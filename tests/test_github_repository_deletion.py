from datetime import datetime, timezone
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import FileChange, GitHubAnalysisJob, GitHubCommit, PullRequest, Repository


class TestGitHubRepositoryDeletion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.TestingSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=cls.test_engine
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

    def test_delete_repository_removes_imported_github_data(self):
        repository = Repository(
            owner="octocat",
            name="hello-world",
            url="https://github.com/octocat/hello-world",
            default_branch="main",
            provider="github_cloud",
        )
        commit = GitHubCommit(
            repository=repository,
            commit_sha="a" * 40,
            message="Initial commit",
            timestamp=datetime.now(timezone.utc),
        )
        pull_request = PullRequest(
            repository=repository,
            pr_number=1,
            title="Add feature",
            status="open",
            base_branch="main",
            head_branch="feature",
            created_at=datetime.now(timezone.utc),
            diff="",
        )
        pull_request.commits.append(commit)
        pull_request.file_changes.append(
            FileChange(
                file_path="README.md",
                change_type="modified",
                lines_added=1,
                lines_deleted=0,
            )
        )
        pull_request.analysis_jobs.append(
            GitHubAnalysisJob(id=str(uuid4()), status="READY_FOR_AST_ANALYSIS")
        )
        self.db.add(repository)
        self.db.commit()
        repository_id = repository.id

        response = self.client.delete(f"/repositories/{repository_id}")

        self.assertEqual(response.status_code, 204)
        self.assertIsNone(
            self.db.query(Repository).filter(Repository.id == repository_id).first()
        )
        self.assertEqual(self.db.query(PullRequest).count(), 0)
        self.assertEqual(self.db.query(GitHubCommit).count(), 0)
        self.assertEqual(self.db.query(FileChange).count(), 0)
        self.assertEqual(self.db.query(GitHubAnalysisJob).count(), 0)

    def test_delete_unknown_repository_returns_not_found(self):
        response = self.client.delete("/repositories/999")

        self.assertEqual(response.status_code, 404)
