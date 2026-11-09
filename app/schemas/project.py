from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProjectCreate(BaseModel):
    name: str = Field(..., description="Unique project name")
    description: Optional[str] = Field(default=None, description="Detailed project description")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2 or len(trimmed) > 120:
            raise ValueError("Project name must be between 2 and 120 characters")
        return trimmed


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, description="Updated project name")
    description: Optional[str] = Field(default=None, description="Updated project description")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            trimmed = value.strip()
            if len(trimmed) < 2 or len(trimmed) > 120:
                raise ValueError("Project name must be between 2 and 120 characters")
            return trimmed
        return value

    @model_validator(mode="after")
    def validate_non_empty(self) -> "ProjectUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field ('name' or 'description') must be provided for update")
        return self


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
