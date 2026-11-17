from sqlalchemy import Column, ForeignKey, Integer, Table

from app.database import Base

pull_request_commits = Table(
    "pull_request_commits",
    Base.metadata,
    Column(
        "pull_request_id",
        Integer,
        ForeignKey("pull_requests.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "commit_id",
        Integer,
        ForeignKey("github_commits.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
