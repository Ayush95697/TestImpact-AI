from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.analysis_run import AnalysisRun
from app.models.change_request import ChangeRequest
from app.models.recommendation import Recommendation
from app.rag.embeddings import CompanyEmbeddingError, CompanyEmbeddingNotConfiguredError
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisRunDetailResponse,
)
from app.schemas.recommendation import (
    RecommendationResponse,
    RecommendationReviewRequest,
    SupportingEvidence,
)
from app.services.impact_analysis import run_impact_analysis

router = APIRouter(
    tags=["Impact Analysis & Recommendations"],
)


@router.post(
    "/change-requests/{change_request_id}/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger regression test impact analysis for a change request",
)
def trigger_impact_analysis(
    change_request_id: int,
    request: AnalysisRequest = AnalysisRequest(),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    """Analyzes a change request using deterministic multi-source heuristics and semantic search.

    Generates ranked regression test case recommendations and records the analysis run.
    """
    # 1. Validate change request existence
    cr = db.query(ChangeRequest).filter(ChangeRequest.id == change_request_id).first()
    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request with ID {change_request_id} not found",
        )

    try:
        result = run_impact_analysis(
            change_request_id=change_request_id,
            top_k=request.top_k,
            db=db,
        )
        return result
    except CompanyEmbeddingNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except CompanyEmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding provider error during retrieval: {str(exc)}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Impact analysis failed: {str(exc)}",
        )


@router.get(
    "/analysis-runs/{analysis_run_id}",
    response_model=AnalysisRunDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve results of an analysis run by ID",
)
def get_analysis_run(
    analysis_run_id: int,
    db: Session = Depends(get_db),
) -> AnalysisRunDetailResponse:
    """Retrieves metadata and ranked recommendations for a historical analysis run."""
    run = db.query(AnalysisRun).filter(AnalysisRun.id == analysis_run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run with ID {analysis_run_id} not found",
        )

    rec_responses = []
    # Recommendations ordered by rank ascending
    for rec in run.recommendations:
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

    return AnalysisRunDetailResponse(
        id=run.id,
        change_request_id=run.change_request_id,
        status=run.status,
        created_at=run.created_at,
        completed_at=run.completed_at,
        total_recommendations=len(rec_responses),
        recommendations=rec_responses,
    )


@router.patch(
    "/recommendations/{recommendation_id}/review",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit QA engineer review decision on a test recommendation",
)
def review_recommendation(
    recommendation_id: int,
    review: RecommendationReviewRequest,
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    """Updates the review status of a test recommendation (accepted or rejected).

    Historical scores, ranking, and supporting evidence are strictly preserved.
    """
    rec = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation with ID {recommendation_id} not found",
        )

    rec.review_status = review.review_status
    db.commit()
    db.refresh(rec)

    return RecommendationResponse(
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

