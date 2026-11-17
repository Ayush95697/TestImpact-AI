# Phase 1 (GitHub Integration) — Database Validation

Validation date: 2026-11-17

## Schema and relationships

`Base.metadata.create_all(bind=engine)` in `app/main.py` is the schema initialization mechanism. No Alembic or other migration files were found.

| Required concept / table | Exists? | Columns | Relationships and constraints |
|---|---|---|---|
| `repositories` | YES | `id`, `name`, `owner`, `url`, `default_branch`, `provider`, `created_at` | One-to-many to `pull_requests` and `github_commits`; delete cascades are configured. Unique (`owner`, `name`). |
| `pull_requests` | YES | `id`, `repository_id`, `pr_number`, `title`, `description`, `author`, `status`, `base_branch`, `head_branch`, `created_at`, `merged_at`, `diff` | `repository_id` references `repositories.id`; one-to-many to `file_changes` and `github_analysis_jobs`; many-to-many to `github_commits` through `pull_request_commits`. Unique (`repository_id`, `pr_number`). |
| `commits` (literal table name) | NO | N/A | Commit data is stored in the `github_commits` table instead. |
| `github_commits` (implemented commit table) | YES | `id`, `repository_id`, `commit_sha`, `author`, `message`, `timestamp` | `repository_id` references `repositories.id`; many-to-many to `pull_requests` via the association table. Unique (`repository_id`, `commit_sha`). |
| `file_changes` | YES | `id`, `pull_request_id`, `file_path`, `previous_filename`, `change_type`, `lines_added`, `lines_deleted`, `patch` | `pull_request_id` references `pull_requests.id`; unique (`pull_request_id`, `file_path`). |
| `pull_request_commits` (association) | YES | `pull_request_id`, `commit_id` | Both columns are foreign keys with cascade behavior and jointly form the primary key. |
| `github_analysis_jobs` (supporting table) | YES | `id`, `pull_request_id`, `status`, `created_at` | `pull_request_id` references `pull_requests.id`; PR relationship is configured to cascade deletes. |

The schema definitions are in `app/models/github.py` and `app/models/github_associations.py`.

## Actual database state

The current configured database resolves to SQLite `./tests/testimpact.db` (as loaded by the current environment and `.env`). It was inspected read-only:

| Table | Exists in configured DB? | Rows at validation |
|---|---:|---:|
| `repositories` | YES | 1 |
| `pull_requests` | YES | 0 |
| `github_commits` | YES | 0 |
| `file_changes` | YES | 0 |
| `pull_request_commits` | YES | 0 |
| `github_analysis_jobs` | YES | 0 |

The existing repository row is `octocat/hello-world`; there are no existing PR, commit, or file-change records. The default-path `testimpact.db` exists but does not contain the GitHub tables. The API tests used an isolated in-memory SQLite database and did not add records to either on-disk database.

## Persistence test and duplicate handling

| Check | Result | Evidence |
|---|---|---|
| Insert repository | PASS | API exercise inserted one repository in the isolated test DB. |
| Insert PR | PASS | API exercise inserted one PR; title and diff were persisted and retrieved. |
| Insert commit | PASS | One commit was persisted with SHA and message. |
| Insert changed file | PASS | One file-change row was persisted and returned by the detail API. |
| Duplicate repository handling | PASS | Re-registering the same owner/name returns HTTP 409; a DB uniqueness constraint also protects it. |
| PR/commit/file re-import | PASS | Re-import updates one PR, commit, and file row rather than duplicating them; each re-import creates a new analysis job. |
| Persistent configured DB contains an imported PR | NOT DEMONSTRATED | Current DB has no imported PR rows. The persistence result above is from the isolated test DB, not a live GitHub import to the configured DB. |

Focused test run: `python -m unittest tests.test_github_integration -v` — **4 tests passed**. It was run with `DATABASE_URL=sqlite:///:memory:` to avoid modifying the configured on-disk DB.
