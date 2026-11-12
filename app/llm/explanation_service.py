from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.llm.config import get_llm_settings
from app.llm.prompts import DEFAULT_BATCH_LABEL, EXPLANATION_PROMPT_TEMPLATE
from app.llm.provider import (
    CompanyLLM,
    CompanyLLMError,
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

SOURCE_CODE_LIMITATION = "The analysis does not inspect actual source-code changes."


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


def _serialize_expected_ids_hint(batch_recs: List[Recommendation]) -> str:
    if not batch_recs:
        return "[]"
    return json.dumps(
        [
            {"recommendation_id": rec.id, "test_case_id": rec.test_case_id}
            for rec in batch_recs
        ],
        separators=(",", ":"),
    )


def _collect_run_ground_truth(
    analysis_run: AnalysisRun,
    db: Session,
) -> Dict[str, Any]:
    """Collects strictly project-isolated context entries and ground-truth maps for an analysis run.

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
        key=lambda rec: (rec.rank, rec.id),
    )

    expected_recs_by_id: Dict[int, Recommendation] = {}
    allowed_evidence_by_rec: Dict[int, Set[Tuple[str, int]]] = {}
    ordered_evidence_keys_by_rec: Dict[int, List[Tuple[str, int]]] = {}
    evidence_catalog: Dict[Tuple[str, int], Dict[str, Any]] = {}
    rec_entries_by_id: Dict[int, Dict[str, Any]] = {}

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
        rec_ordered_keys: List[Tuple[str, int]] = []

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
                rec_ordered_keys.append(key)
                rec_allowed_refs.append(
                    {
                        "source_type": source_type,
                        "source_id": source_id,
                    }
                )

        allowed_evidence_by_rec[rec.id] = rec_allowed_set
        ordered_evidence_keys_by_rec[rec.id] = rec_ordered_keys

        entry: Dict[str, Any] = {
            "recommendation_id": rec.id,
            "test_case_id": rec.test_case_id,
            "test_case_title": rec_tc.title if rec_tc else "Unknown",
            "test_case_priority": rec_tc.priority if rec_tc else None,
            "test_case_modules": rec_tc_modules,
            "rank": rec.rank,
            "score": rec.score,
            "impact_level": rec.impact_level,
            "deterministic_reason": rec.reason,
            "score_breakdown": rec.score_breakdown,
            "allowed_evidence_refs": rec_allowed_refs,
        }
        # Include test steps and expected result directly when not already serialized as test_case evidence
        if ("test_case", rec.test_case_id) not in rec_allowed_set and rec_tc is not None:
            entry["test_case_steps"] = rec_tc.steps
            entry["test_case_expected_result"] = rec_tc.expected_result

        rec_entries_by_id[rec.id] = entry

    return {
        "change_request_metadata": {
            "change_request_title": change_request.title,
            "change_request_description": change_request.description,
            "affected_modules": (
                ", ".join(affected_module_names) if affected_module_names else "None"
            ),
        },
        "ordered_recommendations": ordered_recommendations,
        "expected_recs_by_id": expected_recs_by_id,
        "allowed_evidence_by_rec": allowed_evidence_by_rec,
        "ordered_evidence_keys_by_rec": ordered_evidence_keys_by_rec,
        "evidence_catalog": evidence_catalog,
        "rec_entries_by_id": rec_entries_by_id,
    }


def _build_batch_context(
    batch_recs: List[Recommendation],
    ground_truth: Dict[str, Any],
    batch_label: str = DEFAULT_BATCH_LABEL,
) -> Dict[str, Any]:
    """Constructs prompt inputs and expected ground-truth maps scoped strictly to batch_recs."""
    rec_entries_by_id: Dict[int, Dict[str, Any]] = ground_truth["rec_entries_by_id"]
    evidence_catalog: Dict[Tuple[str, int], Dict[str, Any]] = ground_truth["evidence_catalog"]
    allowed_evidence_by_rec: Dict[int, Set[Tuple[str, int]]] = ground_truth["allowed_evidence_by_rec"]
    ordered_evidence_keys_by_rec: Dict[int, List[Tuple[str, int]]] = ground_truth[
        "ordered_evidence_keys_by_rec"
    ]

    batch_recommendations_context: List[Dict[str, Any]] = []
    batch_expected_recs_by_id: Dict[int, Recommendation] = {}
    batch_allowed_evidence: Dict[int, Set[Tuple[str, int]]] = {}
    batch_evidence_list: List[Dict[str, Any]] = []
    seen_evidence_keys: Set[Tuple[str, int]] = set()

    for rec in batch_recs:
        batch_expected_recs_by_id[rec.id] = rec
        batch_allowed_evidence[rec.id] = allowed_evidence_by_rec[rec.id]
        batch_recommendations_context.append(rec_entries_by_id[rec.id])

        for ev_key in ordered_evidence_keys_by_rec.get(rec.id, []):
            if ev_key not in seen_evidence_keys and ev_key in evidence_catalog:
                seen_evidence_keys.add(ev_key)
                batch_evidence_list.append(evidence_catalog[ev_key])

    prompt_inputs = {
        **ground_truth["change_request_metadata"],
        "batch_label": batch_label,
        "expected_recommendation_ids": _serialize_expected_ids_hint(batch_recs),
        "recommendations_context_json": json.dumps(
            batch_recommendations_context, separators=(",", ":")
        ),
        "supporting_evidence_context_json": json.dumps(
            batch_evidence_list, separators=(",", ":")
        ),
    }

    return {
        "prompt_inputs": prompt_inputs,
        "recommendations": list(batch_recs),
        "expected_recs_by_id": batch_expected_recs_by_id,
        "allowed_evidence_by_rec": batch_allowed_evidence,
    }


def prepare_explanation_context(
    analysis_run: AnalysisRun,
    db: Session,
) -> Dict[str, Any]:
    """Builds strictly project-isolated, plain JSON-serializable prompt inputs and ground-truth maps.

    Never passes raw SQLAlchemy ORM objects to the LLM.
    """
    ground_truth = _collect_run_ground_truth(analysis_run=analysis_run, db=db)
    batch_ctx = _build_batch_context(
        batch_recs=ground_truth["ordered_recommendations"],
        ground_truth=ground_truth,
        batch_label=DEFAULT_BATCH_LABEL,
    )
    return {
        "prompt_inputs": batch_ctx["prompt_inputs"],
        "expected_recs_by_id": batch_ctx["expected_recs_by_id"],
        "allowed_evidence_by_rec": batch_ctx["allowed_evidence_by_rec"],
    }


def prepare_batch_explanation_contexts(
    analysis_run: AnalysisRun,
    db: Session,
    batch_size: int = 3,
) -> Dict[str, Any]:
    """Splits persisted recommendations into deterministic ordered batches with scoped evidence."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    ground_truth = _collect_run_ground_truth(analysis_run=analysis_run, db=db)
    ordered_recs: List[Recommendation] = ground_truth["ordered_recommendations"]

    if not ordered_recs:
        chunks: List[List[Recommendation]] = [[]]
    else:
        chunks = [
            ordered_recs[i : i + batch_size]
            for i in range(0, len(ordered_recs), batch_size)
        ]

    total_batches = len(chunks)
    batch_contexts: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks, start=1):
        label = (
            f"Batch {idx} of {total_batches} ({len(chunk)} recommendation(s))"
        )
        batch_contexts.append(
            _build_batch_context(
                batch_recs=chunk,
                ground_truth=ground_truth,
                batch_label=label,
            )
        )

    return {
        "batches": batch_contexts,
        "ground_truth": ground_truth,
        "ordered_recommendations": ordered_recs,
        "expected_recs_by_id": ground_truth["expected_recs_by_id"],
        "allowed_evidence_by_rec": ground_truth["allowed_evidence_by_rec"],
    }


def _verify_recommendations_against_ground_truth(
    recommendations: List[RecommendationExplanation],
    expected_recs_by_id: Dict[int, Recommendation],
    allowed_evidence_by_rec: Dict[int, Set[Tuple[str, int]]],
    require_complete: bool = True,
) -> Tuple[List[RecommendationExplanation], Set[int]]:
    seen_rec_ids: Set[int] = set()
    validated_recs: List[RecommendationExplanation] = []

    for rec_exp in recommendations:
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
    if require_complete and seen_rec_ids != expected_rec_ids:
        missing_ids = sorted(expected_rec_ids - seen_rec_ids)
        raise CompanyLLMOutputValidationError(
            f"LLM output omitted explanations for persisted recommendation IDs: {missing_ids}"
        )

    # Preserve original deterministic ranking order
    validated_recs.sort(
        key=lambda item: (
            expected_recs_by_id[item.recommendation_id].rank,
            item.recommendation_id,
        )
    )
    return validated_recs, seen_rec_ids


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

    validated_recs, _ = _verify_recommendations_against_ground_truth(
        recommendations=payload.recommendations,
        expected_recs_by_id=expected_recs_by_id,
        allowed_evidence_by_rec=allowed_evidence_by_rec,
        require_complete=True,
    )

    return LLMExplanationPayload(
        overall_summary=payload.overall_summary,
        risk_observations=payload.risk_observations,
        recommendations=validated_recs,
        limitations=payload.limitations,
    )


def _format_validation_error(
    base_message: str,
    llm_instance: CompanyLLM,
    fallback_diag: Optional[str] = None,
) -> str:
    diag = (
        llm_instance.get_truncation_diagnostic()
        if hasattr(llm_instance, "get_truncation_diagnostic")
        else None
    ) or fallback_diag
    if diag:
        return f"{base_message} ({diag})"
    return base_message


def _extract_valid_partial_and_missing(
    raw_output: str,
    batch_recs: List[Recommendation],
    expected_recs_by_id: Dict[int, Recommendation],
    allowed_evidence_by_rec: Dict[int, Set[Tuple[str, int]]],
) -> Optional[
    Tuple[LLMExplanationPayload, List[RecommendationExplanation], List[Recommendation]]
]:
    """Identifies a clean partial omission (valid schema/evidence subset with missing IDs)."""
    if not isinstance(raw_output, str) or not raw_output.strip():
        return None
    try:
        parsed_json = json.loads(raw_output.strip())
        if not isinstance(parsed_json, dict):
            return None
        payload = LLMExplanationPayload.model_validate(parsed_json)
        validated_partial, seen_ids = _verify_recommendations_against_ground_truth(
            recommendations=payload.recommendations,
            expected_recs_by_id=expected_recs_by_id,
            allowed_evidence_by_rec=allowed_evidence_by_rec,
            require_complete=False,
        )
    except (Exception, ValidationError, CompanyLLMOutputValidationError):
        return None

    if not seen_ids or len(seen_ids) >= len(expected_recs_by_id):
        return None

    missing_recs = [rec for rec in batch_recs if rec.id not in seen_ids]
    if not missing_recs:
        return None
    return payload, validated_partial, missing_recs


def _dedupe_text_items(items: List[str]) -> List[str]:
    result: List[str] = []
    seen_lower: Set[str] = set()
    for item in items:
        stripped = item.strip()
        if not stripped:
            continue
        key = stripped.lower()
        if key not in seen_lower:
            seen_lower.add(key)
            result.append(stripped)
    return result


def _merge_payloads(
    payloads: List[LLMExplanationPayload],
    expected_recs_by_id: Dict[int, Recommendation],
    allowed_evidence_by_rec: Dict[int, Set[Tuple[str, int]]],
    ensure_source_code_limitation: bool = True,
) -> LLMExplanationPayload:
    """Merges validated batch payloads and verifies global ID, evidence, and order invariants."""
    if len(payloads) == 1:
        verified_recs, _ = _verify_recommendations_against_ground_truth(
            recommendations=payloads[0].recommendations,
            expected_recs_by_id=expected_recs_by_id,
            allowed_evidence_by_rec=allowed_evidence_by_rec,
            require_complete=True,
        )
        return LLMExplanationPayload(
            overall_summary=payloads[0].overall_summary,
            risk_observations=list(payloads[0].risk_observations),
            recommendations=verified_recs,
            limitations=list(payloads[0].limitations),
        )

    merged_summaries = _dedupe_text_items([p.overall_summary for p in payloads])
    overall_summary = " ".join(merged_summaries) if merged_summaries else ""

    risk_observations = _dedupe_text_items(
        [obs for p in payloads for obs in p.risk_observations]
    )
    limitations = _dedupe_text_items(
        [lim for p in payloads for lim in p.limitations]
    )
    if ensure_source_code_limitation and not any(
        "source-code" in lim.lower() or "source code" in lim.lower()
        for lim in limitations
    ):
        limitations.append(SOURCE_CODE_LIMITATION)

    all_rec_explanations: List[RecommendationExplanation] = [
        rec_exp for p in payloads for rec_exp in p.recommendations
    ]
    verified_recs, _ = _verify_recommendations_against_ground_truth(
        recommendations=all_rec_explanations,
        expected_recs_by_id=expected_recs_by_id,
        allowed_evidence_by_rec=allowed_evidence_by_rec,
        require_complete=True,
    )

    return LLMExplanationPayload(
        overall_summary=overall_summary,
        risk_observations=risk_observations,
        recommendations=verified_recs,
        limitations=limitations,
    )


def _invoke_and_validate_batch(
    chain: Any,
    llm_instance: CompanyLLM,
    batch_ctx: Dict[str, Any],
    ground_truth: Dict[str, Any],
) -> LLMExplanationPayload:
    """Invokes the LLM for a single batch, with one targeted retry on clean partial omissions."""
    raw_output = chain.invoke(batch_ctx["prompt_inputs"])
    initial_diag = (
        llm_instance.get_truncation_diagnostic()
        if hasattr(llm_instance, "get_truncation_diagnostic")
        else None
    )

    try:
        return validate_llm_explanation(
            raw_output=raw_output,
            expected_recs_by_id=batch_ctx["expected_recs_by_id"],
            allowed_evidence_by_rec=batch_ctx["allowed_evidence_by_rec"],
        )
    except CompanyLLMOutputValidationError as initial_exc:
        partial_info = (
            _extract_valid_partial_and_missing(
                raw_output=raw_output,
                batch_recs=batch_ctx["recommendations"],
                expected_recs_by_id=batch_ctx["expected_recs_by_id"],
                allowed_evidence_by_rec=batch_ctx["allowed_evidence_by_rec"],
            )
            if len(batch_ctx["recommendations"]) > 1
            else None
        )

        if partial_info is None:
            raise CompanyLLMOutputValidationError(
                _format_validation_error(
                    str(initial_exc),
                    llm_instance=llm_instance,
                    fallback_diag=initial_diag,
                )
            ) from None

        partial_payload, validated_partial_recs, missing_recs = partial_info
        retry_ctx = _build_batch_context(
            batch_recs=missing_recs,
            ground_truth=ground_truth,
            batch_label=f"{batch_ctx['prompt_inputs']['batch_label']} — recovery for omitted IDs",
        )

        try:
            retry_raw = chain.invoke(retry_ctx["prompt_inputs"])
            retry_payload = validate_llm_explanation(
                raw_output=retry_raw,
                expected_recs_by_id=retry_ctx["expected_recs_by_id"],
                allowed_evidence_by_rec=retry_ctx["allowed_evidence_by_rec"],
            )
        except (CompanyLLMOutputValidationError, CompanyLLMResponseError):
            raise CompanyLLMOutputValidationError(
                _format_validation_error(
                    str(initial_exc),
                    llm_instance=llm_instance,
                    fallback_diag=initial_diag,
                )
            ) from None

        partial_validated_payload = LLMExplanationPayload(
            overall_summary=partial_payload.overall_summary,
            risk_observations=partial_payload.risk_observations,
            recommendations=validated_partial_recs,
            limitations=partial_payload.limitations,
        )
        return _merge_payloads(
            payloads=[partial_validated_payload, retry_payload],
            expected_recs_by_id=batch_ctx["expected_recs_by_id"],
            allowed_evidence_by_rec=batch_ctx["allowed_evidence_by_rec"],
            ensure_source_code_limitation=False,
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
    batch_size: Optional[int] = None,
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

    effective_batch_size = (
        batch_size if batch_size is not None else get_llm_settings().company_llm_batch_size
    )
    batched_context = prepare_batch_explanation_contexts(
        analysis_run=analysis_run,
        db=db,
        batch_size=effective_batch_size,
    )

    chain = EXPLANATION_PROMPT_TEMPLATE | llm_instance
    batch_payloads: List[LLMExplanationPayload] = []

    for batch_ctx in batched_context["batches"]:
        batch_payload = _invoke_and_validate_batch(
            chain=chain,
            llm_instance=llm_instance,
            batch_ctx=batch_ctx,
            ground_truth=batched_context["ground_truth"],
        )
        batch_payloads.append(batch_payload)

    validated_payload = _merge_payloads(
        payloads=batch_payloads,
        expected_recs_by_id=batched_context["expected_recs_by_id"],
        allowed_evidence_by_rec=batched_context["allowed_evidence_by_rec"],
        ensure_source_code_limitation=True,
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

