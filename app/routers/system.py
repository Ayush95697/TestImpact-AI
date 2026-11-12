from collections import defaultdict
from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm.provider import get_llm_model
from app.models.analysis_run import AnalysisRun
from app.models.change_request import ChangeRequest
from app.models.defect import Defect
from app.models.module import Module
from app.models.project import Project
from app.models.recommendation import Recommendation
from app.models.test_case import TestCase
from app.models.test_execution import TestExecution
from app.rag.embeddings import get_embedding_model
from app.schemas.analysis import AnalysisRunSummaryResponse
from app.schemas.system import (
    DashboardSummaryResponse,
    DistributionItem,
    ProjectOverviewItem,
    SystemCapabilitiesResponse,
)

router = APIRouter(tags=["System & Dashboard"])


@router.get(
    "/system/capabilities",
    response_model=SystemCapabilitiesResponse,
    summary="Report backend AI and RAG capability flags without exposing credentials",
)
def get_system_capabilities() -> SystemCapabilitiesResponse:
    """Safely checks whether RAG embeddings and LLM explanation generation are configured."""
    rag_available = False
    llm_explanations_available = False

    try:
        rag_available = bool(get_embedding_model().is_configured())
    except Exception:
        rag_available = False

    try:
        llm_explanations_available = bool(get_llm_model().is_configured())
    except Exception:
        llm_explanations_available = False

    return SystemCapabilitiesResponse(
        rag_available=rag_available,
        llm_explanations_available=llm_explanations_available,
    )


@router.get(
    "/dashboard/summary",
    response_model=DashboardSummaryResponse,
    summary="Read-only aggregate overview metrics and recent analysis runs for the dashboard",
)
def get_dashboard_summary(
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    """Computes read-only counts, distributions, project overviews, and recent analysis activity."""
    total_projects = db.query(func.count(Project.id)).scalar() or 0
    total_modules = db.query(func.count(Module.id)).scalar() or 0
    total_test_cases = db.query(func.count(TestCase.id)).scalar() or 0
    total_defects = db.query(func.count(Defect.id)).scalar() or 0
    total_change_requests = db.query(func.count(ChangeRequest.id)).scalar() or 0
    total_analysis_runs = db.query(func.count(AnalysisRun.id)).scalar() or 0

    module_counts_by_project: Dict[int, int] = dict(
        db.query(Module.project_id, func.count(Module.id))
        .group_by(Module.project_id)
        .all()
    )
    tc_counts_by_project: Dict[int, int] = dict(
        db.query(TestCase.project_id, func.count(TestCase.id))
        .group_by(TestCase.project_id)
        .all()
    )
    defect_counts_by_project: Dict[int, int] = dict(
        db.query(Defect.project_id, func.count(Defect.id))
        .group_by(Defect.project_id)
        .all()
    )
    cr_counts_by_project: Dict[int, int] = dict(
        db.query(ChangeRequest.project_id, func.count(ChangeRequest.id))
        .group_by(ChangeRequest.project_id)
        .all()
    )

    projects = db.query(Project).order_by(Project.id.asc()).all()
    projects_overview: List[ProjectOverviewItem] = [
        ProjectOverviewItem(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
            module_count=int(module_counts_by_project.get(project.id, 0)),
            test_case_count=int(tc_counts_by_project.get(project.id, 0)),
            defect_count=int(defect_counts_by_project.get(project.id, 0)),
            change_request_count=int(cr_counts_by_project.get(project.id, 0)),
        )
        for project in projects
    ]

    impact_rows = (
        db.query(Recommendation.impact_level, func.count(Recommendation.id))
        .group_by(Recommendation.impact_level)
        .all()
    )
    impact_map: Dict[str, int] = defaultdict(int)
    for level, count in impact_rows:
        if level:
            impact_map[str(level)] += int(count)

    ordered_levels = ["High", "Medium", "Low"]
    impact_level_distribution: List[DistributionItem] = []
    if impact_map:
        for level in ordered_levels:
            impact_level_distribution.append(
                DistributionItem(label=level, count=impact_map.get(level, 0))
            )
        for extra_level, extra_count in sorted(impact_map.items()):
            if extra_level not in ordered_levels:
                impact_level_distribution.append(
                    DistributionItem(label=extra_level, count=extra_count)
                )

    exec_rows = (
        db.query(TestExecution.status, func.count(TestExecution.id))
        .group_by(TestExecution.status)
        .all()
    )
    exec_map: Dict[str, int] = defaultdict(int)
    for exec_status, count in exec_rows:
        if exec_status:
            exec_map[str(exec_status).lower()] += int(count)

    ordered_exec_statuses = ["passed", "failed", "blocked"]
    execution_status_distribution: List[DistributionItem] = []
    if exec_map:
        for exec_status in ordered_exec_statuses:
            execution_status_distribution.append(
                DistributionItem(label=exec_status, count=exec_map.get(exec_status, 0))
            )
        for extra_status, extra_count in sorted(exec_map.items()):
            if extra_status not in ordered_exec_statuses:
                execution_status_distribution.append(
                    DistributionItem(label=extra_status, count=extra_count)
                )

    recent_runs = (
        db.query(AnalysisRun)
        .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
        .limit(5)
        .all()
    )

    recent_run_ids = [run.id for run in recent_runs]
    rec_counts_by_run: Dict[int, int] = {}
    if recent_run_ids:
        rec_counts_by_run = dict(
            db.query(Recommendation.analysis_run_id, func.count(Recommendation.id))
            .filter(Recommendation.analysis_run_id.in_(recent_run_ids))
            .group_by(Recommendation.analysis_run_id)
            .all()
        )

    recent_analysis_runs: List[AnalysisRunSummaryResponse] = []
    for run in recent_runs:
        cr = run.change_request
        project = cr.project if cr else None
        recent_analysis_runs.append(
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

    return DashboardSummaryResponse(
        total_projects=int(total_projects),
        total_modules=int(total_modules),
        total_test_cases=int(total_test_cases),
        total_defects=int(total_defects),
        total_change_requests=int(total_change_requests),
        total_analysis_runs=int(total_analysis_runs),
        projects_overview=projects_overview,
        impact_level_distribution=impact_level_distribution,
        execution_status_distribution=execution_status_distribution,
        recent_analysis_runs=recent_analysis_runs,
    )

