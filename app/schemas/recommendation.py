from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, field_validator


class SupportingEvidence(BaseModel):
    source_type: str
    source_id: int
    title: str
    retrieval_rank: Optional[int] = None
    distance: Optional[float] = None
    module_id: Optional[int] = None
    module_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RecommendationResponse(BaseModel):
    id: int
    test_case_id: int
    test_case_title: str
    rank: int
    score: float
    impact_level: str
    reason: str
    score_breakdown: Dict[str, Any]
    supporting_evidence: List[SupportingEvidence]
    review_status: str

    model_config = ConfigDict(from_attributes=True)


class RecommendationReviewRequest(BaseModel):
    review_status: str

    @field_validator("review_status")
    @classmethod
    def validate_review_status(cls, v: str) -> str:
        allowed = {"accepted", "rejected"}
        if v.lower() not in allowed:
            raise ValueError(
                f"Invalid review_status: '{v}'. Must be one of: {sorted(list(allowed))}"
            )
        return v.lower()

