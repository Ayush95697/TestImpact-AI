import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.github import FileChange, GitHubAnalysisJob, GitHubCommit, PullRequest, Repository
from app.services.github_service import GitHubService, GitHubServiceError


class TestGitHubIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=cls.test_engine,
        )
        Base.metadata.create_all(bind=cls.test_engine)

        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=cls.test_engine)
        cls.test_engine.dispose()

    def setUp(self):
        self.db = self.TestingSessionLocal()
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def register_repository(self):
        return self.client.post(
            "/repositories",
            json={
                "owner": "TestImpactAI",
                "name": "enterprise-app",
                "url": "https://github.com/TestImpactAI/enterprise-app",
                "default_branch": "main",
                "provider": "github_cloud",
            },
        )

    def pr_data(self):
        return {
            "number": 27,
            "title": "Improve Authentication Validation",
            "body": "Reject empty tokens",
            "user": {"login": "contributor"},
            "state": "open",
            "merged_at": None,
            "created_at": "2026-01-02T03:04:05Z",
            "base": {"ref": "main"},
            "head": {"ref": "feature/token-validation"},
        }

    def commit_data(self, message="Add token validation"):
        return [
            {
                "sha": "7f82c1d000000000000000000000000000000000",
                "commit": {
                    "message": message,
                    "author": {"name": "Contributor", "date": "2026-01-02T04:05:06Z"},
                    "committer": {"date": "2026-01-02T04:05:06Z"},
                },
                "author": {"login": "contributor"},
            }
        ]

    def file_data(self, path="auth/token.py"):
        return [
            {
                "filename": path,
                "status": "modified",
                "additions": 2,
                "deletions": 1,
                "patch": "@@ -1 +1,2 @@",
            }
        ]

    def configure_mock_service(self, service_class, *, message="Add token validation", path="auth/token.py"):
        service = service_class.return_value
        service.fetch_pull_request.return_value = self.pr_data()
        service.fetch_commits.return_value = self.commit_data(message)
        service.fetch_changed_files.return_value = self.file_data(path)
        service.fetch_diff.return_value = "diff --git a/auth/token.py b/auth/token.py"
        return service

    def test_import_persists_pr_commits_files_and_diff(self):
        repository_response = self.register_repository()
        self.assertEqual(repository_response.status_code, 201)
        repository = repository_response.json()
        self.assertEqual(repository["full_name"], "testimpactai/enterprise-app")

        with patch("app.routers.github.GitHubService") as service_class:
            self.configure_mock_service(service_class)
            response = self.client.post(
                "/analyze-pr",
                json={"repository": "TestImpactAI/enterprise-app", "pr_number": 27},
            )

        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["changed_files"], ["auth/token.py"])
        self.assertEqual(result["commits"], ["7f82c1d000000000000000000000000000000000"])
        self.assertEqual(result["status"], "READY_FOR_AST_ANALYSIS")
        self.assertTrue(result["analysis_job_id"])

        stored_pr = self.db.query(PullRequest).one()
        self.assertEqual(stored_pr.title, "Improve Authentication Validation")
        self.assertIn("diff --git", stored_pr.diff)
        self.assertEqual(stored_pr.file_changes[0].change_type, "modified")
        self.assertEqual(stored_pr.file_changes[0].lines_added, 2)
        self.assertEqual(stored_pr.commits[0].author, "contributor")
        self.assertEqual(stored_pr.commits[0].message, "Add token validation")
        self.assertEqual(self.db.query(GitHubAnalysisJob).one().id, result["analysis_job_id"])

        details = self.client.get(
            f"/repositories/{repository['id']}/pull-requests/27"
        )
        self.assertEqual(details.status_code, 200)
        self.assertEqual(details.json()["changed_files"][0]["file_path"], "auth/token.py")
        self.assertIn("diff --git", details.json()["diff"])

    def test_reimport_updates_data_without_duplicate_pr_commit_or_file(self):
        self.register_repository()
        with patch("app.routers.github.GitHubService") as service_class:
            self.configure_mock_service(service_class)
            first = self.client.post(
                "/analyze-pr",
                json={"repository": "enterprise-app", "pr_number": 27},
            )
            self.configure_mock_service(
                service_class,
                message="Update validation",
                path="auth/session.py",
            )
            second = self.client.post(
                "/analyze-pr",
                json={"repository": "enterprise-app", "pr_number": 27},
            )

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertNotEqual(first.json()["analysis_job_id"], second.json()["analysis_job_id"])
        self.assertEqual(self.db.query(Repository).count(), 1)
        self.assertEqual(self.db.query(PullRequest).count(), 1)
        self.assertEqual(self.db.query(GitHubCommit).count(), 1)
        self.assertEqual(self.db.query(FileChange).count(), 1)
        self.assertEqual(self.db.query(GitHubAnalysisJob).count(), 2)
        self.assertEqual(self.db.query(GitHubCommit).one().message, "Update validation")
        self.assertEqual(self.db.query(FileChange).one().file_path, "auth/session.py")

    def test_duplicate_repository_registration_and_missing_repository(self):
        self.assertEqual(self.register_repository().status_code, 201)
        duplicate = self.register_repository()
        self.assertEqual(duplicate.status_code, 409)

        missing = self.client.post(
            "/analyze-pr",
            json={"repository": "unknown/repository", "pr_number": 1},
        )
        self.assertEqual(missing.status_code, 404)

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"})
    @patch("app.services.github_service.requests.get")
    def test_cloud_api_request_uses_token_and_maps_authentication_errors(self, mock_get):
        successful_response = MagicMock()
        successful_response.status_code = 200
        successful_response.ok = True
        successful_response.json.return_value = {"login": "test-user"}
        mock_get.return_value = successful_response

        service = GitHubService("https://github.com/owner/repo", "github_cloud")
        self.assertEqual(service.check_connection(), {"login": "test-user"})
        self.assertEqual(mock_get.call_args.args[0], "https://api.github.com/user")
        self.assertEqual(
            mock_get.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-token",
        )

        unauthorized_response = MagicMock()
        unauthorized_response.status_code = 401
        unauthorized_response.headers = {}
        unauthorized_response.ok = False
        mock_get.return_value = unauthorized_response
        with self.assertRaises(GitHubServiceError) as error:
            service.check_connection()
        self.assertEqual(error.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
