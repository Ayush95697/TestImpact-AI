from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ModuleCreate(BaseModel):
    name: str = Field(..., description="Name of the module")
    description: Optional[str] = Field(default=None, description="Module description")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 2 or len(trimmed) > 120:
            raise ValueError("Module name must be between 2 and 120 characters")
        return trimmed


class ModuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, description="Updated module name")
    description: Optional[str] = Field(default=None, description="Updated module description")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            trimmed = value.strip()
            if len(trimmed) < 2 or len(trimmed) > 120:
                raise ValueError("Module name must be between 2 and 120 characters")
            return trimmed
        return value

    @model_validator(mode="after")
    def validate_non_empty(self) -> "ModuleUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field ('name' or 'description') must be provided for update")
        return self


class ModuleResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

