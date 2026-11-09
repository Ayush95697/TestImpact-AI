from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TestCaseCreate(BaseModel):
    project_id: int = Field(..., description="ID of the parent project")
    title: str = Field(..., description="Test case title")
    steps: str = Field(..., description="Test execution steps")
    expected_result: str = Field(..., description="Expected outcome")
    priority: str = Field(..., description="Priority level (e.g. Low, Medium, High, Critical)")
    module_ids: List[int] = Field(..., min_length=1, description="List of associated module IDs (at least 1 required)")

    @field_validator("title", "steps", "expected_result", "priority")
    @classmethod
    def validate_non_empty_strings(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Field cannot be empty or whitespace only")
        return trimmed

    @field_validator("module_ids")
    @classmethod
    def validate_module_ids(cls, ids: List[int]) -> List[int]:
        if not ids:
            raise ValueError("At least one module ID must be provided")
        deduped = list(dict.fromkeys(ids))
        for m_id in deduped:
            if m_id <= 0:
                raise ValueError("Module IDs must be positive integers")
        return deduped


class TestCaseUpdate(BaseModel):
    title: Optional[str] = Field(default=None, description="Updated title")
    steps: Optional[str] = Field(default=None, description="Updated execution steps")
    expected_result: Optional[str] = Field(default=None, description="Updated expected outcome")
    priority: Optional[str] = Field(default=None, description="Updated priority level")
    module_ids: Optional[List[int]] = Field(default=None, description="Updated list of associated module IDs")

    @field_validator("title", "steps", "expected_result", "priority")
    @classmethod
    def validate_optional_strings(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            trimmed = value.strip()
            if not trimmed:
                raise ValueError("Field cannot be empty or whitespace only")
            return trimmed
        return value

    @field_validator("module_ids")
    @classmethod
    def validate_module_ids(cls, ids: Optional[List[int]]) -> Optional[List[int]]:
        if ids is not None:
            if len(ids) == 0:
                raise ValueError("When module_ids is provided, at least one module ID must be specified")
            deduped = list(dict.fromkeys(ids))
            for m_id in deduped:
                if m_id <= 0:
                    raise ValueError("Module IDs must be positive integers")
            return deduped
        return ids

    @model_validator(mode="after")
    def validate_non_empty(self) -> "TestCaseUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided for update")
        return self


class TestCaseResponse(BaseModel):
    id: int
    project_id: int
    title: str
    steps: str
    expected_result: str
    priority: str
    module_ids: List[int]

    model_config = ConfigDict(from_attributes=True)

