from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class IndexRequest(BaseModel):
    project_id: int = Field(..., description="ID of the project to index")


class IndexResponse(BaseModel):
    project_id: int
    total_indexed: int
    test_cases_indexed: int
    defects_indexed: int
    test_executions_indexed: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class SearchRequest(BaseModel):
    project_id: int = Field(..., description="ID of the project to search within")
    query: str = Field(..., description="Search query string")
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of most relevant documents to retrieve (1-20)",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Query cannot be empty or whitespace only")
        return trimmed


class SearchResult(BaseModel):
    page_content: str
    source_type: str
    source_id: int
    project_id: int
    distance: Optional[float] = Field(
        default=None,
        description="Vector distance score (lower represents higher semantic similarity)",
    )

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    project_id: int
    query: str
    total_results: int
    results: List[SearchResult]

    model_config = ConfigDict(from_attributes=True)

