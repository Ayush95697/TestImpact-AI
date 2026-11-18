from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Repository(Base):
    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("owner", "name", name="uq_github_repository_owner_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    owner: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    pull_requests: Mapped[List["PullRequest"]] = relationship(
        "PullRequest", back_populates="repository", cascade="all, delete-orphan"
    )
    commits: Mapped[List["GitHubCommit"]] = relationship(
        "GitHubCommit", back_populates="repository", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (
        UniqueConstraint("repository_id", "pr_number", name="uq_github_pull_request_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    base_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    head_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    merged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    diff: Mapped[str] = mapped_column(Text, nullable=False, default="")

    repository: Mapped["Repository"] = relationship("Repository", back_populates="pull_requests")
    file_changes: Mapped[List["FileChange"]] = relationship(
        "FileChange", back_populates="pull_request", cascade="all, delete-orphan"
    )
    commits: Mapped[List["GitHubCommit"]] = relationship(
        "GitHubCommit", secondary="pull_request_commits", back_populates="pull_requests"
    )
    analysis_jobs: Mapped[List["GitHubAnalysisJob"]] = relationship(
        "GitHubAnalysisJob", back_populates="pull_request", cascade="all, delete-orphan"
    )


class GitHubCommit(Base):
    __tablename__ = "github_commits"
    __table_args__ = (UniqueConstraint("repository_id", "commit_sha", name="uq_github_commit_sha"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="commits")
    pull_requests: Mapped[List["PullRequest"]] = relationship(
        "PullRequest", secondary="pull_request_commits", back_populates="commits"
    )


class FileChange(Base):
    __tablename__ = "file_changes"
    __table_args__ = (
        UniqueConstraint("pull_request_id", "file_path", name="uq_github_file_change_path"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pull_request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    previous_filename: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    lines_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lines_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    patch: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    pull_request: Mapped["PullRequest"] = relationship("PullRequest", back_populates="file_changes")


class GitHubAnalysisJob(Base):
    __tablename__ = "github_analysis_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    pull_request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    pull_request: Mapped["PullRequest"] = relationship("PullRequest", back_populates="analysis_jobs")
