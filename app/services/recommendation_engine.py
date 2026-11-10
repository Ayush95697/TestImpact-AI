from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

from app.models.change_request import ChangeRequest
from app.models.defect import Defect
from app.models.module import Module
from app.models.test_case import TestCase
from app.models.test_execution import TestExecution

# Configurable deterministic scoring weights
SCORING_WEIGHTS: Dict[str, float] = {
    "direct_module_match": 40.0,
    "semantic_search_match": 25.0,
    "related_defect_match": 20.0,
    "related_execution_match": 15.0,
}


class CandidateRecord:
    """Internal candidate container collecting evidence from all sources."""

    def __init__(self, test_case: TestCase):
        self.test_case = test_case
        self.direct_module_evidence: List[Dict[str, Any]] = []
        self.semantic_search_evidence: List[Dict[str, Any]] = []
        self.defect_evidence: List[Dict[str, Any]] = []
        self.execution_evidence: List[Dict[str, Any]] = []
        self.best_semantic_rank: Optional[int] = None
        self.best_overall_retrieval_rank: int = 999999


def determine_impact_level(score: float) -> str:
    """Classifies a score into heuristic impact levels.

    These are heuristic decision-support recommendations, not statistical probabilities.
    """
    if score >= 70.0:
        return "High"
    elif score >= 40.0:
        return "Medium"
    elif score > 0.0:
        return "Low"
    else:
        return "Low"


def build_recommendation_candidates(
    change_request: ChangeRequest,
    retrieved_records: List[Dict[str, Any]],
    db: Session,
    weights: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """Generates, scores, and ranks deduplicated test case recommendations deterministically.

    Steps:
    1. Direct Module Matches: Finds test cases belonging to the change request's affected modules.
    2. Semantic Document Matches: Evaluates test cases retrieved directly by RAG.
    3. Defect Expansion: Finds test cases associated with modules of retrieved historical defects.
    4. Execution Mapping: Resolves test cases from retrieved execution records.
    5. Deduplication & Evidence Consolidation: Tracks all supporting evidence per unique test_case_id.
    6. Deterministic Scoring: Computes weights (maximum 100) and detailed score breakdown.
    7. Multi-Tier Ranking: Sorts candidates and assigns sequential 1-based ranks.
    """
    active_weights = weights or SCORING_WEIGHTS
    project_id = change_request.project_id
    affected_module_ids: Set[int] = {m.id for m in change_request.modules}
    affected_modules_by_id: Dict[int, Module] = {m.id: m for m in change_request.modules}

    candidates: Dict[int, CandidateRecord] = {}

    def get_or_create_candidate(tc: TestCase) -> CandidateRecord:
        if tc.id not in candidates:
            candidates[tc.id] = CandidateRecord(tc)
        return candidates[tc.id]

    # ------------------------------------------------------------------
    # 1. CANDIDATE GENERATION: Direct Affected Module Matches
    # ------------------------------------------------------------------
    if affected_module_ids:
        direct_module_tcs = (
            db.query(TestCase)
            .join(TestCase.modules)
            .filter(
                TestCase.project_id == project_id,
                Module.id.in_(affected_module_ids),
            )
            .all()
        )
        for tc in direct_module_tcs:
            cand = get_or_create_candidate(tc)
            for m in tc.modules:
                if m.id in affected_module_ids:
                    # Avoid duplicate evidence for the same module
                    if not any(e["source_id"] == m.id for e in cand.direct_module_evidence):
                        cand.direct_module_evidence.append(
                            {
                                "source_type": "module",
                                "source_id": m.id,
                                "title": f"Affected Module: {m.name}",
                                "module_id": m.id,
                                "module_name": m.name,
                            }
                        )

    # ------------------------------------------------------------------
    # 2. CANDIDATE GENERATION & EVIDENCE: RAG Retrieved Records
    # ------------------------------------------------------------------
    for idx, record in enumerate(retrieved_records):
        retrieval_rank = idx + 1
        source_type = record.get("source_type")
        source_id = record.get("source_id")
        distance = record.get("distance")

        if not source_id or not source_type:
            continue

        if source_type == "test_case":
            # Re-fetch from relational database with project validation
            tc = (
                db.query(TestCase)
                .filter(TestCase.id == source_id, TestCase.project_id == project_id)
                .first()
            )
            if tc:
                cand = get_or_create_candidate(tc)
                cand.semantic_search_evidence.append(
                    {
                        "source_type": "test_case",
                        "source_id": tc.id,
                        "title": tc.title,
                        "retrieval_rank": retrieval_rank,
                        "distance": distance,
                    }
                )
                if cand.best_semantic_rank is None or retrieval_rank < cand.best_semantic_rank:
                    cand.best_semantic_rank = retrieval_rank
                if retrieval_rank < cand.best_overall_retrieval_rank:
                    cand.best_overall_retrieval_rank = retrieval_rank

        elif source_type == "defect":
            defect = (
                db.query(Defect)
                .filter(Defect.id == source_id, Defect.project_id == project_id)
                .first()
            )
            if defect and defect.module_id:
                related_tcs = (
                    db.query(TestCase)
                    .join(TestCase.modules)
                    .filter(
                        TestCase.project_id == project_id,
                        Module.id == defect.module_id,
                    )
                    .all()
                )
                for tc in related_tcs:
                    cand = get_or_create_candidate(tc)
                    # Deduplicate evidence for the same defect
                    if not any(e["source_id"] == defect.id for e in cand.defect_evidence):
                        cand.defect_evidence.append(
                            {
                                "source_type": "defect",
                                "source_id": defect.id,
                                "title": defect.title,
                                "retrieval_rank": retrieval_rank,
                                "distance": distance,
                                "module_id": defect.module_id,
                                "module_name": defect.module.name if defect.module else None,
                            }
                        )
                    if retrieval_rank < cand.best_overall_retrieval_rank:
                        cand.best_overall_retrieval_rank = retrieval_rank

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
            if execution and execution.test_case:
                tc = execution.test_case
                cand = get_or_create_candidate(tc)
                if not any(e["source_id"] == execution.id for e in cand.execution_evidence):
                    cand.execution_evidence.append(
                        {
                            "source_type": "test_execution",
                            "source_id": execution.id,
                            "title": f"Execution ({execution.status}) build {execution.build_version or 'N/A'}",
                            "retrieval_rank": retrieval_rank,
                            "distance": distance,
                        }
                    )
                if retrieval_rank < cand.best_overall_retrieval_rank:
                    cand.best_overall_retrieval_rank = retrieval_rank

    # ------------------------------------------------------------------
    # 3. SCORING, EXPLANATION, AND EVIDENCE PACKAGING
    # ------------------------------------------------------------------
    scored_candidates: List[Dict[str, Any]] = []

    for cand in candidates.values():
        has_direct_module = len(cand.direct_module_evidence) > 0
        has_semantic_search = len(cand.semantic_search_evidence) > 0
        has_related_defect = len(cand.defect_evidence) > 0
        has_related_execution = len(cand.execution_evidence) > 0

        score_breakdown = {
            "direct_module_match": (
                active_weights["direct_module_match"] if has_direct_module else 0.0
            ),
            "semantic_search_match": (
                active_weights["semantic_search_match"] if has_semantic_search else 0.0
            ),
            "related_defect_match": (
                active_weights["related_defect_match"] if has_related_defect else 0.0
            ),
            "related_execution_match": (
                active_weights["related_execution_match"] if has_related_execution else 0.0
            ),
        }
        total_score = min(100.0, max(0.0, sum(score_breakdown.values())))
        impact_level = determine_impact_level(total_score)

        # Consolidate all evidence items into a unified list
        all_evidence: List[Dict[str, Any]] = []
        all_evidence.extend(cand.direct_module_evidence)
        all_evidence.extend(cand.semantic_search_evidence)
        all_evidence.extend(cand.defect_evidence)
        all_evidence.extend(cand.execution_evidence)

        # Construct transparent deterministic explanation
        reasons: List[str] = []
        if has_direct_module:
            mod_names = ", ".join(
                sorted(
                    {
                        e["module_name"]
                        for e in cand.direct_module_evidence
                        if e.get("module_name")
                    }
                )
            )
            reasons.append(
                f"The test case is directly associated with the {mod_names} module affected by this change."
            )
        if has_semantic_search:
            reasons.append(
                f"Retrieved directly by semantic search matching the change request (rank #{cand.best_semantic_rank})."
            )
        if has_related_defect:
            defect_names = ", ".join(
                f"'{e['title']}'" for e in cand.defect_evidence[:2]
            )
            reasons.append(
                f"Related historical defect ({defect_names}) was retrieved in the same module."
            )
        if has_related_execution:
            exec_statuses = ", ".join(
                e["title"] for e in cand.execution_evidence[:2]
            )
            reasons.append(
                f"Historical test execution history ({exec_statuses}) was retrieved."
            )

        explanation = (
            " ".join(reasons)
            if reasons
            else "Identified as a regression test candidate."
        )

        scored_candidates.append(
            {
                "test_case_id": cand.test_case.id,
                "test_case_title": cand.test_case.title,
                "score": round(total_score, 2),
                "impact_level": impact_level,
                "reason": explanation,
                "score_breakdown": score_breakdown,
                "supporting_evidence": all_evidence,
                "direct_module_count": len(cand.direct_module_evidence),
                "best_semantic_rank": (
                    cand.best_semantic_rank
                    if cand.best_semantic_rank is not None
                    else 999999
                ),
                "best_overall_retrieval_rank": cand.best_overall_retrieval_rank,
            }
        )

    # ------------------------------------------------------------------
    # 4. MULTI-TIER DETERMINISTIC RANKING
    # ------------------------------------------------------------------
    # Rank sorting criteria:
    # 1. Higher score first
    # 2. More direct affected-module matches
    # 3. Better direct semantic retrieval rank
    # 4. Better overall retrieval rank
    # 5. Lower test_case_id as stable final tie-breaker
    scored_candidates.sort(
        key=lambda item: (
            -item["score"],
            -item["direct_module_count"],
            item["best_semantic_rank"],
            item["best_overall_retrieval_rank"],
            item["test_case_id"],
        )
    )

    # Assign sequential ranks starting from 1
    for rank_idx, item in enumerate(scored_candidates):
        item["rank"] = rank_idx + 1

    return scored_candidates

