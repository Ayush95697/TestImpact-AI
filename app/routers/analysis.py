from datetime import date, datetime, time, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm.explanation_service import (
    AnalysisExplanationNotFoundError,
    AnalysisRunNotCompletedError,
    AnalysisRunNotFoundError,
    generate_analysis_explanation,
    get_analysis_explanation,
)
from app.llm.provider import CompanyLLMError, CompanyLLMNotConfiguredError
from app.models.analysis_run import AnalysisRun
from app.models.change_request import ChangeRequest
from app.models.project import Project
from app.models.recommendation import Recommendation
from app.rag.embeddings import CompanyEmbeddingError, CompanyEmbeddingNotConfiguredError
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisRunDetailResponse,
    AnalysisRunListResponse,
    AnalysisRunSummaryResponse,
)
from app.schemas.llm import AnalysisExplanationResponse
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
    "/analysis-runs",
    response_model=AnalysisRunListResponse,
    status_code=status.HTTP_200_OK,
    summary="List persisted analysis runs with optional filtering and pagination",
)
def list_analysis_runs(
    project_id: Optional[int] = Query(None, ge=1, description="Filter analysis runs by project ID"),
    change_request_id: Optional[int] = Query(None, ge=1, description="Filter analysis runs by change request ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by analysis status (running, completed, failed)"),
    date_from: Optional[date] = Query(None, description="Inclusive start UTC date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="Inclusive end UTC date (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of analysis runs to return"),
    offset: int = Query(0, ge=0, description="Number of analysis runs to skip"),
    db: Session = Depends(get_db),
) -> AnalysisRunListResponse:
    """Returns paginated persisted analysis runs ordered newest-first."""
    query = (
        db.query(AnalysisRun, ChangeRequest, Project)
        .outerjoin(ChangeRequest, AnalysisRun.change_request_id == ChangeRequest.id)
        .outerjoin(Project, ChangeRequest.project_id == Project.id)
    )

    if project_id is not None:
        query = query.filter(ChangeRequest.project_id == project_id)

    if change_request_id is not None:
        query = query.filter(AnalysisRun.change_request_id == change_request_id)

    if status_filter is not None and status_filter.strip():
        query = query.filter(AnalysisRun.status == status_filter.strip().lower())

    if date_from is not None:
        start_dt = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        query = query.filter(AnalysisRun.created_at >= start_dt)

    if date_to is not None:
        end_dt = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
        query = query.filter(AnalysisRun.created_at <= end_dt)

    total = query.count()
    rows = (
        query.order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    run_ids = [run.id for run, _, _ in rows]
    rec_counts_by_run: Dict[int, int] = {}
    if run_ids:
        rec_counts_by_run = dict(
            db.query(Recommendation.analysis_run_id, func.count(Recommendation.id))
            .filter(Recommendation.analysis_run_id.in_(run_ids))
            .group_by(Recommendation.analysis_run_id)
            .all()
        )

    items: List[AnalysisRunSummaryResponse] = []
    for run, cr, project in rows:
        items.append(
            AnalysisRunSummaryResponse(
                id=run.id,
                change_request_id=run.change_request_id,
                change_request_title=cr.title if cr else None,
                project_id=cr.project_id if cr else None,
                project_name=project.name if project else None,
                status=run.status,
                total_recommendations=int(rec_counts_by_run.get(run.id, 0)),
                created_at=run.created_at,
                completed_at=run.completed_at,
            )
        )

    return AnalysisRunListResponse(
        total=int(total),
        limit=limit,
        offset=offset,
        items=items,
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


@router.post(
    "/analysis-runs/{analysis_run_id}/explain",
    response_model=AnalysisExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate an evidence-grounded LLM explanation for an existing analysis run",
)
def explain_analysis_run(
    analysis_run_id: int,
    db: Session = Depends(get_db),
) -> AnalysisExplanationResponse:
    """Generates and persists a Company LLM explanation for existing deterministic recommendations.

    Does not modify recommendation scores, ranks, impact levels, supporting evidence, or review status.
    """
    try:
        return generate_analysis_explanation(analysis_run_id=analysis_run_id, db=db)
    except AnalysisRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except CompanyLLMNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except AnalysisRunNotCompletedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except CompanyLLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Company LLM provider error: {str(exc)}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate analysis explanation: {str(exc)}",
        )


@router.get(
    "/analysis-runs/{analysis_run_id}/explanation",
    response_model=AnalysisExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve the persisted LLM explanation for an analysis run",
)
def get_analysis_run_explanation(
    analysis_run_id: int,
    db: Session = Depends(get_db),
) -> AnalysisExplanationResponse:
    """Returns the previously persisted LLM explanation for an analysis run."""
    try:
        return get_analysis_explanation(analysis_run_id=analysis_run_id, db=db)
    except (AnalysisRunNotFoundError, AnalysisExplanationNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

