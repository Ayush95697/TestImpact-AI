from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun
from app.models.change_request import ChangeRequest
from app.models.recommendation import Recommendation
from app.rag.retrieval import search_project_knowledge
from app.schemas.analysis import AnalysisResponse
from app.schemas.recommendation import RecommendationResponse, SupportingEvidence
from app.services.recommendation_engine import build_recommendation_candidates


def run_impact_analysis(
    change_request_id: int,
    top_k: int = 10,
    db: Session = None,
) -> AnalysisResponse:
    """Performs end-to-end regression impact analysis for a change request.

    1. Fetches and validates the ChangeRequest and its associated modules.
    2. Builds a deterministic semantic query reflecting the proposed changes.
    3. Retrieves historical project context via project-isolated Chroma vector search.
    4. Generates, scores, and ranks test case recommendations deterministically.
    5. Persists the AnalysisRun and its Recommendation records.
    6. Returns the structured AnalysisResponse.
    """
    if db is None:
        raise ValueError("Database session must be provided")

    # 1. Fetch ChangeRequest
    change_request = (
        db.query(ChangeRequest)
        .filter(ChangeRequest.id == change_request_id)
        .first()
    )
    if not change_request:
        return None

    # 2. Build semantic search query
    module_names = [m.name for m in change_request.modules]
    modules_str = ", ".join(module_names) if module_names else "None"
    semantic_query = (
        f"Change Request: {change_request.title}. "
        f"Description: {change_request.description}. "
        f"Affected Modules: {modules_str}."
    )

    # 3. Create initial AnalysisRun in 'running' state
    analysis_run = AnalysisRun(
        change_request_id=change_request.id,
        status="running",
    )
    db.add(analysis_run)
    db.commit()
    db.refresh(analysis_run)

    try:
        # 4. Perform vector retrieval with strict project isolation
        retrieved_records = search_project_knowledge(
            project_id=change_request.project_id,
            query=semantic_query,
            top_k=top_k,
        )

        # 5. Generate and rank recommendations deterministically
        ranked_candidates = build_recommendation_candidates(
            change_request=change_request,
            retrieved_records=retrieved_records,
            db=db,
        )

        # 6. Persist recommendations
        recommendation_objects = []
        for item in ranked_candidates:
            rec = Recommendation(
                analysis_run_id=analysis_run.id,
                test_case_id=item["test_case_id"],
                rank=item["rank"],
                score=item["score"],
                impact_level=item["impact_level"],
                reason=item["reason"],
                score_breakdown=item["score_breakdown"],
                supporting_evidence=item["supporting_evidence"],
                review_status="pending",
            )
            db.add(rec)
            recommendation_objects.append(rec)

        analysis_run.status = "completed"
        analysis_run.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(analysis_run)

        # 7. Construct and return response
        rec_responses = []
        for rec in analysis_run.recommendations:
            rec_responses.append(
                RecommendationResponse(
                    id=rec.id,
                    test_case_id=rec.test_case_id,
                    test_case_title=rec.test_case.title if rec.test_case else "Unknown",
                    rank=rec.rank,
                    score=rec.score,
                    impact_level=rec.impact_level,
                    reason=rec.reason,
                    score_breakdown=rec.score_breakdown,
                    supporting_evidence=[
                        SupportingEvidence(**ev) for ev in rec.supporting_evidence
                    ],
                    review_status=rec.review_status,
                )
            )

        return AnalysisResponse(
            analysis_run_id=analysis_run.id,
            change_request_id=change_request.id,
            project_id=change_request.project_id,
            status=analysis_run.status,
            total_recommendations=len(rec_responses),
            recommendations=rec_responses,
        )

    except Exception as exc:
        db.rollback()
        analysis_run.status = "failed"
        analysis_run.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise exc

