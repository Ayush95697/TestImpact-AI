from datetime import datetime
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class RepositoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    owner: str = Field(..., min_length=1, max_length=120)
    url: HttpUrl
    default_branch: str = Field(..., min_length=1, max_length=255)
    provider: Literal["github_cloud", "github_enterprise"]

    @field_validator("name", "owner", "default_branch")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Field must not be blank")
        return trimmed

    @model_validator(mode="after")
    def validate_repository_url(self) -> "RepositoryCreate":
        parsed = urlparse(str(self.url))
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Repository URL must not contain credentials, query, or fragment")
        path_parts = [part for part in parsed.path.strip("/").split("/") if part]
        if len(path_parts) != 2:
            raise ValueError("Repository URL path must contain owner and repository name")
        if path_parts[0].casefold() != self.owner.casefold():
            raise ValueError("Repository URL path must match the supplied owner")
        if path_parts[-1].removesuffix(".git").casefold() != self.name.casefold():
            raise ValueError("Repository URL path must match the supplied repository name")
        is_github_cloud = parsed.hostname == "github.com"
        if (self.provider == "github_cloud") != is_github_cloud:
            raise ValueError("Provider must match the GitHub host in the repository URL")
        return self


class RepositoryResponse(BaseModel):
    id: int
    name: str
    owner: str
    full_name: str
    url: str
    default_branch: str
    provider: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AnalyzePRRequest(BaseModel):
    repository: str = Field(..., min_length=1, description="Registered repository name or owner/name")
    pr_number: int = Field(..., gt=0)

    @field_validator("repository")
    @classmethod
    def strip_repository(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Repository must not be blank")
        return trimmed


class FileChangeResponse(BaseModel):
    file_path: str
    previous_filename: Optional[str] = None
    change_type: str
    lines_added: int
    lines_deleted: int


class PullRequestResponse(BaseModel):
    pr_number: int
    title: str
    description: Optional[str] = None
    author: Optional[str] = None
    status: str
    base_branch: str
    head_branch: str
    created_at: datetime
    merged_at: Optional[datetime] = None
    diff: str
    changed_files: list[FileChangeResponse]
    commits: list[str]


class AnalyzePRResponse(BaseModel):
    repository: str
    pr_number: int
    analysis_job_id: str
    changed_files: list[str]
    commits: list[str]
    status: Literal["READY_FOR_AST_ANALYSIS"]


class GitHubConnectionResponse(BaseModel):
    connected: bool
    login: str
    provider: str
