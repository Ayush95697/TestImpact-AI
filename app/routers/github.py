from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.github import FileChange, GitHubAnalysisJob, GitHubCommit, PullRequest, Repository
from app.schemas.github import (
    AnalyzePRRequest,
    AnalyzePRResponse,
    FileChangeResponse,
    GitHubConnectionResponse,
    PullRequestResponse,
    RepositoryCreate,
    RepositoryResponse,
)
from app.services.github_service import GitHubService, GitHubServiceError

router = APIRouter(tags=["GitHub"])


@router.post("/repositories", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
def register_repository(repository_in: RepositoryCreate, db: Session = Depends(get_db)) -> RepositoryResponse:
    owner = repository_in.owner.casefold()
    name = repository_in.name.casefold()
    existing = db.query(Repository).filter(
        func.lower(Repository.owner) == owner,
        func.lower(Repository.name) == name,
    ).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Repository '{owner}/{name}' is already registered")

    repository = Repository(
        name=name,
        owner=owner,
        url=str(repository_in.url).rstrip("/"),
        default_branch=repository_in.default_branch,
        provider=repository_in.provider,
    )
    db.add(repository)
    try:
        db.commit()
        db.refresh(repository)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"Repository '{owner}/{name}' is already registered") from exc
    return repository


@router.get("/repositories", response_model=List[RepositoryResponse])
def list_repositories(db: Session = Depends(get_db)) -> List[RepositoryResponse]:
    return db.query(Repository).order_by(Repository.owner, Repository.name).all()


@router.delete(
    "/repositories/{repository_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a registered repository",
)
def delete_repository(repository_id: int, db: Session = Depends(get_db)) -> None:
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if repository is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Repository with ID {repository_id} is not registered",
        )

    db.delete(repository)
    db.commit()


@router.get("/github/connection", response_model=GitHubConnectionResponse)
def verify_github_connection(
    repository: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> GitHubConnectionResponse:
    if repository:
        repo = _find_repository(db, repository)
        provider = repo.provider
        repository_url = repo.url
    else:
        provider = "github_cloud"
        repository_url = "https://github.com"
    try:
        service = GitHubService(repository_url=repository_url, provider=provider)
        user = service.check_connection()
    except GitHubServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return GitHubConnectionResponse(connected=True, login=user["login"], provider=provider)


@router.post("/analyze-pr", response_model=AnalyzePRResponse)
def analyze_pull_request(request: AnalyzePRRequest, db: Session = Depends(get_db)) -> AnalyzePRResponse:
    repository = _find_repository(db, request.repository)
    try:
        service = GitHubService(repository_url=repository.url, provider=repository.provider)
        pull_request_data = service.fetch_pull_request(repository.owner, repository.name, request.pr_number)
        commit_data = service.fetch_commits(repository.owner, repository.name, request.pr_number)
        file_data = service.fetch_changed_files(repository.owner, repository.name, request.pr_number)
        diff = service.fetch_diff(repository.owner, repository.name, request.pr_number)
        imported = _validate_pull_request_data(
            pull_request_data, commit_data, file_data, request.pr_number, diff
        )
    except GitHubServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    pull_request = db.query(PullRequest).filter(
        PullRequest.repository_id == repository.id,
        PullRequest.pr_number == request.pr_number,
    ).first()
    if pull_request is None:
        pull_request = PullRequest(
            repository_id=repository.id,
            pr_number=request.pr_number,
            **imported["pull_request"],
        )
        db.add(pull_request)
        db.flush()
    else:
        for field, value in imported["pull_request"].items():
            setattr(pull_request, field, value)
        pull_request.file_changes.clear()

    commits: List[GitHubCommit] = []
    for commit_data_item in imported["commits"]:
        commit = db.query(GitHubCommit).filter(
            GitHubCommit.repository_id == repository.id,
            GitHubCommit.commit_sha == commit_data_item["commit_sha"],
        ).first()
        if commit is None:
            commit = GitHubCommit(repository_id=repository.id, **commit_data_item)
            db.add(commit)
        else:
            for field, value in commit_data_item.items():
                setattr(commit, field, value)
        commits.append(commit)

    pull_request.commits = commits
    for file_change in imported["file_changes"]:
        pull_request.file_changes.append(FileChange(**file_change))

    job_id = str(uuid4())
    db.add(GitHubAnalysisJob(id=job_id, pull_request_id=pull_request.id, status="READY_FOR_AST_ANALYSIS"))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "GitHub pull request data conflicted with an existing import") from exc

    return AnalyzePRResponse(
        repository=repository.full_name,
        pr_number=request.pr_number,
        analysis_job_id=job_id,
        changed_files=[change["file_path"] for change in imported["file_changes"]],
        commits=[commit["commit_sha"] for commit in imported["commits"]],
        status="READY_FOR_AST_ANALYSIS",
    )


@router.get("/repositories/{repository_id}/pull-requests/{pr_number}", response_model=PullRequestResponse)
def get_imported_pull_request(repository_id: int, pr_number: int, db: Session = Depends(get_db)) -> PullRequestResponse:
    pull_request = db.query(PullRequest).filter(
        PullRequest.repository_id == repository_id,
        PullRequest.pr_number == pr_number,
    ).first()
    if not pull_request:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Pull request #{pr_number} has not been imported for repository {repository_id}",
        )
    return PullRequestResponse(
        pr_number=pull_request.pr_number,
        title=pull_request.title,
        description=pull_request.description,
        author=pull_request.author,
        status=pull_request.status,
        base_branch=pull_request.base_branch,
        head_branch=pull_request.head_branch,
        created_at=pull_request.created_at,
        merged_at=pull_request.merged_at,
        diff=pull_request.diff,
        changed_files=[
            FileChangeResponse(
                file_path=file.file_path,
                previous_filename=file.previous_filename,
                change_type=file.change_type,
                lines_added=file.lines_added,
                lines_deleted=file.lines_deleted,
            )
            for file in pull_request.file_changes
        ],
        commits=[commit.commit_sha for commit in pull_request.commits],
    )


def _find_repository(db: Session, repository_name: str) -> Repository:
    normalized = repository_name.strip().casefold()
    if "/" in normalized:
        owner, name = normalized.split("/", 1)
        repository = db.query(Repository).filter(
            func.lower(Repository.owner) == owner,
            func.lower(Repository.name) == name,
        ).first()
    else:
        matches = db.query(Repository).filter(
            func.lower(Repository.name) == normalized
        ).order_by(Repository.id.asc()).limit(2).all()
        if len(matches) > 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "Repository name is ambiguous; use the owner/name form")
        repository = matches[0] if matches else None
    if repository is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Repository '{repository_name}' is not registered")
    return repository


def _validate_pull_request_data(
    pull_request: Dict[str, Any],
    commits: List[Dict[str, Any]],
    files: List[Dict[str, Any]],
    expected_number: int,
    diff: str,
) -> Dict[str, Any]:
    try:
        if pull_request.get("number") != expected_number:
            raise ValueError("Pull request number did not match the request")
        base_data = pull_request.get("base")
        head_data = pull_request.get("head")
        if not isinstance(base_data, dict) or not isinstance(head_data, dict):
            raise ValueError("Pull request branch data is invalid")
        base_branch = base_data["ref"]
        head_branch = head_data["ref"]
        author_data = pull_request.get("user") or {}
        merged_at = _parse_github_datetime(pull_request.get("merged_at"), optional=True)
        state = pull_request["state"]
        status_value = "merged" if merged_at is not None else state
        pr_values = {
            "title": pull_request["title"],
            "description": pull_request.get("body"),
            "author": author_data.get("login") if isinstance(author_data, dict) else None,
            "status": status_value,
            "base_branch": base_branch,
            "head_branch": head_branch,
            "created_at": _parse_github_datetime(pull_request.get("created_at")),
            "merged_at": merged_at,
            "diff": diff,
        }
        if state not in {"open", "closed"}:
            raise ValueError("Pull request status is invalid")
        if not isinstance(pr_values["title"], str) or not pr_values["title"]:
            raise ValueError("Pull request title is invalid")
        return {
            "pull_request": pr_values,
            "commits": [_validate_commit(commit) for commit in commits],
            "file_changes": [_validate_file(file) for file in files],
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise GitHubServiceError(502, f"GitHub returned invalid pull request data: {exc}") from exc


def _validate_commit(commit: Dict[str, Any]) -> Dict[str, Any]:
    sha = commit.get("sha")
    details = commit.get("commit")
    if not isinstance(details, dict):
        raise ValueError("Commit details are invalid")
    author_data = details.get("author") or {}
    committer_data = details.get("committer") or {}
    user_data = commit.get("author") or {}
    timestamp = author_data.get("date") or committer_data.get("date")
    author_name = user_data.get("login") or author_data.get("name")
    message = details["message"]
    if not isinstance(sha, str) or not sha or not isinstance(message, str):
        raise ValueError("Commit SHA or message is invalid")
    return {
        "commit_sha": sha,
        "author": author_name if isinstance(author_name, str) else None,
        "message": message,
        "timestamp": _parse_github_datetime(timestamp),
    }


def _validate_file(file: Dict[str, Any]) -> Dict[str, Any]:
    filename = file["filename"]
    status_value = file["status"]
    status_map = {"added": "added", "modified": "modified", "removed": "deleted", "renamed": "renamed"}
    if not isinstance(filename, str) or not filename:
        raise ValueError("Changed file path is invalid")
    if status_value not in status_map:
        raise ValueError(f"Unknown changed file status '{status_value}'")
    additions = file.get("additions", 0)
    deletions = file.get("deletions", 0)
    if not isinstance(additions, int) or additions < 0 or not isinstance(deletions, int) or deletions < 0:
        raise ValueError("Changed file line counts are invalid")
    patch = file.get("patch")
    if patch is not None and not isinstance(patch, str):
        raise ValueError("Changed file patch is invalid")
    previous_filename = file.get("previous_filename")
    return {
        "file_path": filename,
        "previous_filename": previous_filename if isinstance(previous_filename, str) else None,
        "change_type": status_map[status_value],
        "lines_added": additions,
        "lines_deleted": deletions,
        "patch": patch,
    }


def _parse_github_datetime(value: Any, optional: bool = False) -> Optional[datetime]:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("GitHub timestamp is missing or invalid")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
