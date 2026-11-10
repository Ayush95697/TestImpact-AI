from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_EXECUTION_STATUSES = {"passed", "failed", "blocked"}


class TestExecutionCreate(BaseModel):
    test_case_id: int = Field(..., description="ID of the test case executed")
    status: str = Field(..., description="Execution status: passed, failed, or blocked")
    build_version: Optional[str] = Field(default=None, description="Build or version identifier")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_EXECUTION_STATUSES:
            raise ValueError(
                f"Invalid execution status '{value}'. Must be one of: {', '.join(sorted(VALID_EXECUTION_STATUSES))}"
            )
        return normalized

    @field_validator("build_version")
    @classmethod
    def validate_build_version(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            trimmed = value.strip()
            return trimmed if trimmed else None
        return value


class TestExecutionResponse(BaseModel):
    id: int
    test_case_id: int
    status: str
    build_version: Optional[str] = None
    executed_at: datetime

    model_config = ConfigDict(from_attributes=True)

