from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.recommendation import RecommendationResponse


class AnalysisRequest(BaseModel):
    top_k: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Number of candidate records to retrieve from vector store",
    )


class AnalysisResponse(BaseModel):
    analysis_run_id: int
    change_request_id: int
    project_id: int
    status: str
    total_recommendations: int
    recommendations: List[RecommendationResponse]

    model_config = ConfigDict(from_attributes=True)


class AnalysisRunDetailResponse(BaseModel):
    id: int
    change_request_id: Optional[int]
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    total_recommendations: int
    recommendations: List[RecommendationResponse]

    model_config = ConfigDict(from_attributes=True)

