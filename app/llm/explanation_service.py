from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.llm.prompts import EXPLANATION_PROMPT_TEMPLATE
from app.llm.provider import (
    CompanyLLM,
    CompanyLLMNotConfiguredError,
    CompanyLLMResponseError,
    get_llm_model,
)
from app.models.analysis_explanation import AnalysisExplanation
from app.models.analysis_run import AnalysisRun
from app.models.defect import Defect
from app.models.module import Module
from app.models.recommendation import Recommendation
from app.models.test_case import TestCase
from app.models.test_execution import TestExecution
from app.schemas.llm import (
    AnalysisExplanationResponse,
    EvidenceReference,
    LLMExplanationPayload,
    RecommendationExplanation,
)


class AnalysisRunNotFoundError(Exception):
    """Raised when the requested analysis run (or its parent change request) does not exist."""


class AnalysisExplanationNotFoundError(Exception):
    """Raised when no LLM explanation has been generated for an analysis run."""


class AnalysisRunNotCompletedError(Exception):
    """Raised when explanation generation is requested for an analysis run that has not completed."""


class CompanyLLMOutputValidationError(CompanyLLMResponseError):
    """Raised when generated LLM output violates JSON, schema, or evidence grounding constraints."""


def _serialize_defect(defect: Defect, project_id: int) -> Dict[str, Any]:
    module_names = (
        [defect.module.name]
        if defect.module and defect.module.project_id == project_id
        else []
    )
    return {
        "source_type": "defect",
        "source_id": defect.id,
        "title": defect.title,
        "severity": defect.severity,
        "description": defect.description,
        "resolution_notes": defect.resolution_notes or "None recorded",
        "module_names": module_names,
    }


def _serialize_test_case(test_case: TestCase, project_id: int) -> Dict[str, Any]:
    module_names = [m.name for m in test_case.modules if m.project_id == project_id]
    return {
        "source_type": "test_case",
        "source_id": test_case.id,
        "title": test_case.title,
        "priority": test_case.priority,
        "description": f"Steps: {test_case.steps}\nExpected Result: {test_case.expected_result}",
        "module_names": module_names,
    }


def _serialize_test_execution(execution: TestExecution, project_id: int) -> Dict[str, Any]:
    tc = execution.test_case
    module_names = [m.name for m in tc.modules if m.project_id == project_id] if tc else []
    tc_title = tc.title if tc else "Unknown"
    return {
        "source_type": "test_execution",
        "source_id": execution.id,
        "title": f"Execution ({execution.status}) build {execution.build_version or 'N/A'} - {tc_title}",
        "test_case_id": execution.test_case_id,
        "test_case_title": tc_title,
        "execution_status": execution.status,
        "build_version": execution.build_version,
        "executed_at": execution.executed_at.isoformat() if execution.executed_at else None,
        "description": (
            f"Historical execution of test case '{tc_title}' with status '{execution.status}' "
            f"on build '{execution.build_version or 'N/A'}'."
        ),
        "module_names": module_names,
    }


def _serialize_module(module: Module) -> Dict[str, Any]:
    return {
        "source_type": "module",
        "source_id": module.id,
        "title": f"Affected Module: {module.name}",
        "description": module.description or "No module description provided.",
        "module_names": [module.name],
    }


def prepare_explanation_context(
    analysis_run: AnalysisRun,
    db: Session,
) -> Dict[str, Any]:
    """Builds strictly project-isolated, plain JSON-serializable prompt inputs and ground-truth maps.

    Never passes raw SQLAlchemy ORM objects to the LLM.
    """
    change_request = analysis_run.change_request
    if change_request is None:
        raise AnalysisRunNotFoundError(
            f"Associated change request for analysis run {analysis_run.id} was not found"
        )

    project_id = change_request.project_id
    affected_module_names = [
        m.name for m in change_request.modules if m.project_id == project_id
    ]

    ordered_recommendations = sorted(
        analysis_run.recommendations,
        key=lambda rec: rec.rank,
    )

    expected_recs_by_id: Dict[int, Recommendation] = {}
    allowed_evidence_by_rec: Dict[int, Set[Tuple[str, int]]] = {}
    evidence_catalog: Dict[Tuple[str, int], Dict[str, Any]] = {}
    recommendations_context: List[Dict[str, Any]] = []

    for rec in ordered_recommendations:
        expected_recs_by_id[rec.id] = rec

        rec_tc = (
            db.query(TestCase)
            .filter(TestCase.id == rec.test_case_id, TestCase.project_id == project_id)
            .first()
        )
        rec_tc_modules = (
            [m.name for m in rec_tc.modules if m.project_id == project_id]
            if rec_tc
            else []
        )

        rec_allowed_refs: List[Dict[str, Any]] = []
        rec_allowed_set: Set[Tuple[str, int]] = set()

        for ev in rec.supporting_evidence or []:
            if not isinstance(ev, dict):
                continue
            source_type = ev.get("source_type") or ev.get("evidence_type")
            source_id = ev.get("source_id")
            if (
                not isinstance(source_type, str)
                or isinstance(source_id, bool)
                or not isinstance(source_id, int)
            ):
                continue

            key = (source_type, source_id)
            serialized: Optional[Dict[str, Any]] = evidence_catalog.get(key)

            if serialized is None:
                if source_type == "defect":
                    defect = (
                        db.query(Defect)
                        .filter(Defect.id == source_id, Defect.project_id == project_id)
                        .first()
                    )
                    if defect:
                        serialized = _serialize_defect(defect, project_id)
                elif source_type == "test_case":
                    tc = (
                        db.query(TestCase)
                        .filter(TestCase.id == source_id, TestCase.project_id == project_id)
                        .first()
                    )
                    if tc:
                        serialized = _serialize_test_case(tc, project_id)
                elif source_type == "test_execution":
                    execution = (
                        db.query(TestExecution)
                        .join(TestExecution.test_case)
                        .filter(
                            TestExecution.id == source_id,
                            TestCase.project_id == project_id,
                        )
                        .first()
                    )
                    if execution:
                        serialized = _serialize_test_execution(execution, project_id)
                elif source_type == "module":
                    module = (
                        db.query(Module)
                        .filter(Module.id == source_id, Module.project_id == project_id)
                        .first()
                    )
                    if module:
                        serialized = _serialize_module(module)

                if serialized is not None:
                    evidence_catalog[key] = serialized

            if serialized is not None and key not in rec_allowed_set:
                rec_allowed_set.add(key)
                rec_allowed_refs.append(
                    {
                        "source_type": source_type,
                        "source_id": source_id,
                    }
                )

        allowed_evidence_by_rec[rec.id] = rec_allowed_set

        recommendations_context.append(
            {
                "recommendation_id": rec.id,
                "test_case_id": rec.test_case_id,
                "test_case_title": rec_tc.title if rec_tc else "Unknown",
                "test_case_priority": rec_tc.priority if rec_tc else None,
                "test_case_modules": rec_tc_modules,
                "test_case_steps": rec_tc.steps if rec_tc else None,
                "test_case_expected_result": rec_tc.expected_result if rec_tc else None,
                "rank": rec.rank,
                "score": rec.score,
                "impact_level": rec.impact_level,
                "deterministic_reason": rec.reason,
                "score_breakdown": rec.score_breakdown,
                "allowed_evidence_refs": rec_allowed_refs,
            }
        )

    supporting_evidence_list = list(evidence_catalog.values())

    prompt_inputs = {
        "change_request_title": change_request.title,
        "change_request_description": change_request.description,
        "affected_modules": ", ".join(affected_module_names) if affected_module_names else "None",
        "recommendations_context_json": json.dumps(recommendations_context, indent=2),
        "supporting_evidence_context_json": json.dumps(supporting_evidence_list, indent=2),
    }

    return {
        "prompt_inputs": prompt_inputs,
        "expected_recs_by_id": expected_recs_by_id,
        "allowed_evidence_by_rec": allowed_evidence_by_rec,
    }


def validate_llm_explanation(
    raw_output: str,
    expected_recs_by_id: Dict[int, Recommendation],
    allowed_evidence_by_rec: Dict[int, Set[Tuple[str, int]]],
) -> LLMExplanationPayload:
    """Strictly parses and validates generated LLM JSON output against persisted ground truth."""
    if not isinstance(raw_output, str) or not raw_output.strip():
        raise CompanyLLMOutputValidationError("LLM returned empty explanation output")

    try:
        parsed_json = json.loads(raw_output.strip())
    except Exception:
        raise CompanyLLMOutputValidationError(
            "LLM output is not valid JSON; raw JSON object without Markdown fences is required"
        ) from None

    if not isinstance(parsed_json, dict):
        raise CompanyLLMOutputValidationError(
            "LLM output JSON must be a top-level JSON object"
        )

    try:
        payload = LLMExplanationPayload.model_validate(parsed_json)
    except ValidationError as exc:
        raise CompanyLLMOutputValidationError(
            f"LLM explanation output failed schema validation: {exc}"
        ) from None

    seen_rec_ids: Set[int] = set()
    validated_recs: List[RecommendationExplanation] = []

    for rec_exp in payload.recommendations:
        rec_id = rec_exp.recommendation_id
        if rec_id not in expected_recs_by_id:
            raise CompanyLLMOutputValidationError(
                f"LLM output referenced unknown recommendation_id {rec_id}"
            )
        if rec_id in seen_rec_ids:
            raise CompanyLLMOutputValidationError(
                f"LLM output contained duplicate explanation for recommendation_id {rec_id}"
            )
        seen_rec_ids.add(rec_id)

        expected_rec = expected_recs_by_id[rec_id]
        if rec_exp.test_case_id != expected_rec.test_case_id:
            raise CompanyLLMOutputValidationError(
                f"LLM output mismatched test_case_id for recommendation {rec_id}: "
                f"expected {expected_rec.test_case_id}, got {rec_exp.test_case_id}"
            )

        allowed_refs = allowed_evidence_by_rec.get(rec_id, set())
        seen_ev_keys: Set[Tuple[str, int]] = set()
        deduped_refs: List[EvidenceReference] = []

        for ev_ref in rec_exp.evidence_refs:
            key = (ev_ref.source_type, ev_ref.source_id)
            if key not in allowed_refs:
                raise CompanyLLMOutputValidationError(
                    f"LLM output referenced invented or unverified evidence "
                    f"({ev_ref.source_type}, {ev_ref.source_id}) for recommendation {rec_id}"
                )
            if key not in seen_ev_keys:
                seen_ev_keys.add(key)
                deduped_refs.append(ev_ref)

        validated_recs.append(
            RecommendationExplanation(
                recommendation_id=rec_exp.recommendation_id,
                test_case_id=rec_exp.test_case_id,
                explanation=rec_exp.explanation,
                evidence_refs=deduped_refs,
            )
        )

    expected_rec_ids = set(expected_recs_by_id.keys())
    if seen_rec_ids != expected_rec_ids:
        missing_ids = sorted(expected_rec_ids - seen_rec_ids)
        raise CompanyLLMOutputValidationError(
            f"LLM output omitted explanations for persisted recommendation IDs: {missing_ids}"
        )

    # Preserve original deterministic ranking order
    validated_recs.sort(key=lambda item: expected_recs_by_id[item.recommendation_id].rank)

    return LLMExplanationPayload(
        overall_summary=payload.overall_summary,
        risk_observations=payload.risk_observations,
        recommendations=validated_recs,
        limitations=payload.limitations,
    )


def _to_response(record: AnalysisExplanation) -> AnalysisExplanationResponse:
    return AnalysisExplanationResponse(
        analysis_run_id=record.analysis_run_id,
        model_name=record.model_name,
        overall_summary=record.overall_summary,
        risk_observations=list(record.risk_observations or []),
        recommendations=[
            RecommendationExplanation(**item)
            for item in (record.recommendation_explanations or [])
        ],
        limitations=list(record.limitations or []),
        created_at=record.created_at,
    )


def generate_analysis_explanation(
    analysis_run_id: int,
    db: Session,
    llm: Optional[CompanyLLM] = None,
) -> AnalysisExplanationResponse:
    """Generates, validates, and persists an LLM explanation for an existing completed analysis run."""
    analysis_run = (
        db.query(AnalysisRun).filter(AnalysisRun.id == analysis_run_id).first()
    )
    if not analysis_run:
        raise AnalysisRunNotFoundError(
            f"Analysis run with ID {analysis_run_id} not found"
        )
    if analysis_run.change_request is None:
        raise AnalysisRunNotFoundError(
            f"Associated change request for analysis run {analysis_run_id} not found"
        )

    llm_instance = llm or get_llm_model()
    if not llm_instance.is_configured():
        raise CompanyLLMNotConfiguredError()

    if analysis_run.status != "completed":
        raise AnalysisRunNotCompletedError(
            f"Analysis run {analysis_run_id} has status '{analysis_run.status}'; "
            "only completed analysis runs can be explained"
        )

    context = prepare_explanation_context(analysis_run=analysis_run, db=db)

    chain = EXPLANATION_PROMPT_TEMPLATE | llm_instance
    raw_output = chain.invoke(context["prompt_inputs"])

    validated_payload = validate_llm_explanation(
        raw_output=raw_output,
        expected_recs_by_id=context["expected_recs_by_id"],
        allowed_evidence_by_rec=context["allowed_evidence_by_rec"],
    )

    now = datetime.now(timezone.utc)
    serialized_recs = [rec.model_dump() for rec in validated_payload.recommendations]

    existing = (
        db.query(AnalysisExplanation)
        .filter(AnalysisExplanation.analysis_run_id == analysis_run.id)
        .first()
    )
    if existing:
        existing.model_name = llm_instance.model
        existing.overall_summary = validated_payload.overall_summary
        existing.risk_observations = validated_payload.risk_observations
        existing.recommendation_explanations = serialized_recs
        existing.limitations = validated_payload.limitations
        existing.created_at = now
        record = existing
    else:
        record = AnalysisExplanation(
            analysis_run_id=analysis_run.id,
            model_name=llm_instance.model,
            overall_summary=validated_payload.overall_summary,
            risk_observations=validated_payload.risk_observations,
            recommendation_explanations=serialized_recs,
            limitations=validated_payload.limitations,
            created_at=now,
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return _to_response(record)


def get_analysis_explanation(
    analysis_run_id: int,
    db: Session,
) -> AnalysisExplanationResponse:
    """Retrieves a previously persisted LLM explanation for an analysis run."""
    analysis_run = (
        db.query(AnalysisRun).filter(AnalysisRun.id == analysis_run_id).first()
    )
    if not analysis_run:
        raise AnalysisRunNotFoundError(
            f"Analysis run with ID {analysis_run_id} not found"
        )

    explanation = (
        db.query(AnalysisExplanation)
        .filter(AnalysisExplanation.analysis_run_id == analysis_run_id)
        .first()
    )
    if not explanation:
        raise AnalysisExplanationNotFoundError(
            f"No explanation has been generated for analysis run {analysis_run_id}"
        )

    return _to_response(explanation)

