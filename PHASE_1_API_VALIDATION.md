# Phase 1 (GitHub Integration) — API Validation

Validation date: 2026-11-17

The following GitHub endpoints are registered in the FastAPI OpenAPI schema.

| Method | Route | Request model / parameters | Response model | Purpose |
|---|---|---|---|---|
| `POST` | `/repositories` | JSON `RepositoryCreate` | `RepositoryResponse` (201) | Register a Cloud or Enterprise repository. |
| `GET` | `/repositories` | None | `List[RepositoryResponse]` | Return registered repository information. There is no single-repository GET endpoint. |
| `GET` | `/github/connection` | Optional query parameter `repository` | `GitHubConnectionResponse` | Verify token authentication, optionally using the registered repository's provider/host. |
| `POST` | `/analyze-pr` | JSON `AnalyzePRRequest` (`repository`, positive `pr_number`) | `AnalyzePRResponse` | Fetch PR metadata, commits, changed files, and diff; validate and persist them; create an analysis job. |
| `GET` | `/repositories/{repository_id}/pull-requests/{pr_number}` | Path parameters `repository_id`, `pr_number` | `PullRequestResponse` | Return stored PR metadata, diff, changed-file data, and commit SHAs. |

## API-level test checks

An additional isolated in-memory API exercise used a mocked `GitHubService`; the existing focused suite also mocks GitHub transport/service calls. Results:

| Check | Result | Notes |
|---|---|---|
| Test A — Fetch Repository | PASS for registered repository data | `POST /repositories` returned 201 and `GET /repositories` returned the repository. No endpoint fetches a repository directly from GitHub. |
| Test B — Fetch PR Metadata | PASS | Imported PR detail returned the requested number, title, author, and state. |
| Test C — Fetch Changed Files | PASS | Imported PR detail returned the changed-file path and change metadata. |
| Test D — Fetch Commits (SHA and message) | PARTIAL / FAIL against the stated response expectation | Import fetches commit SHA/message and persists both. PR detail returns SHA strings only; it has no commit-message field or separate commit endpoint. |
| Test E — Fetch Diff | PASS | Imported PR detail returned the persisted diff text. |

These are mocked upstream API checks, not live GitHub tests. No target repository/PR was specified, so authentication or retrieval against GitHub itself was not attempted. The focused suite result was **4 passed**.

## Error handling observed in code

- Missing token: `GitHubServiceError` maps to HTTP 503.
- Invalid/non-positive configured timeout: HTTP 500.
- Request timeout or transport failure: HTTP 503.
- Invalid token: HTTP 401.
- Insufficient access: HTTP 403; rate limit: HTTP 429.
- Missing GitHub repo/PR: HTTP 404.
- Other GitHub non-success response: HTTP 502.
- Invalid JSON or malformed PR/commit/file payload: HTTP 502.
- Unregistered repository: HTTP 404; ambiguous short repository name: HTTP 409.
- Duplicate repository: HTTP 409; DB integrity conflict during import: HTTP 409.
- Missing imported PR detail: HTTP 404.

The focused tests directly exercised successful token-header construction, 401 mapping, duplicate repository registration, unknown repository handling, successful persistence, and re-import update behavior. Other mappings were inspected in the implementation but were not separately exercised in this test run.

## End-to-end scope and remaining gap

The mocked end-to-end route test passes through repository registration, `POST /analyze-pr`, persistence of PR/commit/file/diff data, analysis-job creation, and `GET` of imported PR details. Live GitHub connectivity and persistent PR import into the currently configured on-disk database remain unverified. To meet the stated commit output expectation, expose commit messages in the PR detail response or add a commit retrieval endpoint and corresponding test.
