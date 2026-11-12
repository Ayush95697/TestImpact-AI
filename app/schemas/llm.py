from datetime import datetime
from typing import Any, List
from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_EVIDENCE_SOURCE_TYPES = {"defect", "test_case", "test_execution", "module"}


class EvidenceReference(BaseModel):
    """Reference to an existing persisted supporting evidence record."""

    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(
        ...,
        description="Evidence source type (defect, test_case, test_execution, module)",
    )
    source_id: int = Field(
        ...,
        gt=0,
        description="Persisted identifier of the referenced source record",
    )

    @field_validator("source_type", mode="before")
    @classmethod
    def validate_source_type(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("source_type must be a non-empty string")
        normalized = value.strip()
        if normalized not in ALLOWED_EVIDENCE_SOURCE_TYPES:
            raise ValueError(
                f"Invalid evidence source_type '{normalized}'. "
                f"Must be one of: {sorted(ALLOWED_EVIDENCE_SOURCE_TYPES)}"
            )
        return normalized

    @field_validator("source_id", mode="before")
    @classmethod
    def validate_source_id_int(cls, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("source_id must be a positive integer")
        return value


class RecommendationExplanation(BaseModel):
    """Evidence-grounded LLM explanation for a single existing recommendation."""

    model_config = ConfigDict(extra="forbid")

    recommendation_id: int = Field(..., gt=0)
    test_case_id: int = Field(..., gt=0)
    explanation: str = Field(..., min_length=1)
    evidence_refs: List[EvidenceReference] = Field(default_factory=list)

    @field_validator("recommendation_id", "test_case_id", mode="before")
    @classmethod
    def validate_strict_int_ids(cls, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("ID fields must be positive integers")
        return value

    @field_validator("explanation")
    @classmethod
    def validate_explanation_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("explanation must be a non-empty string")
        return stripped


class LLMExplanationPayload(BaseModel):
    """Strict schema validating raw JSON output returned by the Company LLM."""

    model_config = ConfigDict(extra="forbid")

    overall_summary: str = Field(..., min_length=1)
    risk_observations: List[str] = Field(default_factory=list)
    recommendations: List[RecommendationExplanation] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)

    @field_validator("overall_summary")
    @classmethod
    def validate_overall_summary(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("overall_summary must be a non-empty string")
        return stripped

    @field_validator("risk_observations", "limitations")
    @classmethod
    def validate_string_items(cls, items: List[str]) -> List[str]:
        cleaned: List[str] = []
        for item in items:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("All list items must be non-empty strings")
            cleaned.append(item.strip())
        return cleaned


class AnalysisExplanationResponse(BaseModel):
    """Persisted and API response model for an analysis run's LLM explanation."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    analysis_run_id: int
    model_name: str
    overall_summary: str
    risk_observations: List[str]
    recommendations: List[RecommendationExplanation]
    limitations: List[str]
    created_at: datetime

