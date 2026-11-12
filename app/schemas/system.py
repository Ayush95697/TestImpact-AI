from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from app.schemas.analysis import AnalysisRunSummaryResponse


class SystemCapabilitiesResponse(BaseModel):
    """Safe feature availability flags derived from active backend configuration."""

    rag_available: bool
    llm_explanations_available: bool

    model_config = ConfigDict(from_attributes=True)


class ProjectOverviewItem(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    module_count: int
    test_case_count: int
    defect_count: int
    change_request_count: int

    model_config = ConfigDict(from_attributes=True)


class DistributionItem(BaseModel):
    label: str
    count: int

    model_config = ConfigDict(from_attributes=True)


class DashboardSummaryResponse(BaseModel):
    """Read-only aggregate metrics and distributions for the Dashboard."""

    total_projects: int
    total_modules: int
    total_test_cases: int
    total_defects: int
    total_change_requests: int
    total_analysis_runs: int
    projects_overview: List[ProjectOverviewItem]
    impact_level_distribution: List[DistributionItem]
    execution_status_distribution: List[DistributionItem]
    recent_analysis_runs: List[AnalysisRunSummaryResponse]

    model_config = ConfigDict(from_attributes=True)

