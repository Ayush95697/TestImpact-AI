from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DefectCreate(BaseModel):
    project_id: int = Field(..., description="ID of the parent project")
    module_id: int = Field(..., description="ID of the primary module")
    title: str = Field(..., description="Defect title")
    description: str = Field(..., description="Detailed defect description")
    resolution_notes: Optional[str] = Field(default=None, description="Notes on defect resolution")
    severity: str = Field(..., description="Severity level (e.g. Low, Medium, High, Critical)")

    @field_validator("title", "description", "severity")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Field cannot be empty or whitespace only")
        return trimmed


class DefectUpdate(BaseModel):
    title: Optional[str] = Field(default=None, description="Updated title")
    description: Optional[str] = Field(default=None, description="Updated description")
    resolution_notes: Optional[str] = Field(default=None, description="Updated resolution notes")
    severity: Optional[str] = Field(default=None, description="Updated severity level")

    @field_validator("title", "description", "severity")
    @classmethod
    def validate_optional_strings(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            trimmed = value.strip()
            if not trimmed:
                raise ValueError("Field cannot be empty or whitespace only")
            return trimmed
        return value

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "DefectUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided for update")
        return self


class DefectResponse(BaseModel):
    id: int
    project_id: int
    module_id: int
    title: str
    description: str
    resolution_notes: Optional[str] = None
    severity: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

