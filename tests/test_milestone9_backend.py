from datetime import date, datetime, timedelta, timezone
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import (
    AnalysisRun,
    ChangeRequest,
    Defect,
    Module,
    Project,
    Recommendation,
    TestCase,
    TestExecution,
)
from app.rag.config import get_rag_settings
from app.rag.embeddings import get_embedding_model


class TestMilestone9BackendSuite(unittest.TestCase):
    """Tests for minimal Milestone 9 backend additions: CORS, capabilities, dashboard summary & analysis run listing."""

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

    def test_01_system_capabilities_unconfigured_and_configured_without_leaks(self):
        clean_env = {
            "COMPANY_EMBEDDING_API_URL": "",
            "COMPANY_EMBEDDING_API_KEY": "",
            "COMPANY_LLM_API_URL": "",
            "COMPANY_LLM_API_KEY": "",
            "COMPANY_LLM_MODEL_NAME": "",
        }
        with patch.dict(os.environ, clean_env, clear=False):
            get_rag_settings.cache_clear()
            get_embedding_model.cache_clear()
            resp = self.client.get("/system/capabilities")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(
                data,
                {"rag_available": False, "llm_explanations_available": False},
            )

        configured_env = {
            "COMPANY_EMBEDDING_API_URL": "https://secret.emb.internal/v2/embeddings",
            "COMPANY_EMBEDDING_API_KEY": "super-secret-emb-key-1234",
            "COMPANY_EMBEDDING_DIMENSIONS": "736",
            "COMPANY_LLM_API_URL": "https://secret.llm.internal/v2/chat",
            "COMPANY_LLM_API_KEY": "super-secret-llm-key-5678",
            "COMPANY_LLM_MODEL_NAME": "llama-3-1-8b",
        }
        with patch.dict(os.environ, configured_env, clear=False):
            get_rag_settings.cache_clear()
            get_embedding_model.cache_clear()
            resp = self.client.get("/system/capabilities")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(
                data,
                {"rag_available": True, "llm_explanations_available": True},
            )
            serialized = resp.text
            self.assertNotIn("secret", serialized.lower())
            self.assertNotIn("key", serialized.lower())
            self.assertNotIn("http", serialized.lower())

        get_rag_settings.cache_clear()
        get_embedding_model.cache_clear()

    def test_02_dashboard_summary_empty_database(self):
        resp = self.client.get("/dashboard/summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_projects"], 0)
        self.assertEqual(data["total_modules"], 0)
        self.assertEqual(data["total_test_cases"], 0)
        self.assertEqual(data["total_defects"], 0)
        self.assertEqual(data["total_change_requests"], 0)
        self.assertEqual(data["total_analysis_runs"], 0)
        self.assertEqual(data["projects_overview"], [])
        self.assertEqual(data["impact_level_distribution"], [])
        self.assertEqual(data["execution_status_distribution"], [])
        self.assertEqual(data["recent_analysis_runs"], [])

    def test_03_dashboard_summary_and_analysis_runs_listing_and_filters(self):
        p1 = Project(name="Core Banking", description="Financial backend")
        p2 = Project(name="Shop Portal", description="Retail app")
        self.db.add_all([p1, p2])
        self.db.flush()

        m1 = Module(project_id=p1.id, name="Auth", description="Auth module")
        m2 = Module(project_id=p1.id, name="Transfers", description="Wire module")
        m3 = Module(project_id=p2.id, name="Cart", description="Cart module")
        self.db.add_all([m1, m2, m3])
        self.db.flush()

        tc1 = TestCase(
            project_id=p1.id,
            title="Login success",
            steps="1. Login",
            expected_result="200 OK",
            priority="High",
            modules=[m1],
        )
        tc2 = TestCase(
            project_id=p2.id,
            title="Cart add item",
            steps="1. Add item",
            expected_result="Cart updated",
            priority="Medium",
            modules=[m3],
        )
        self.db.add_all([tc1, tc2])
        self.db.flush()

        d1 = Defect(
            project_id=p1.id,
            module_id=m1.id,
            title="Token expiry race",
            description="Expires under load",
            severity="High",
        )
        self.db.add(d1)

        ex1 = TestExecution(test_case_id=tc1.id, status="passed", build_version="1.0.0")
        ex2 = TestExecution(test_case_id=tc1.id, status="failed", build_version="1.0.1")
        ex3 = TestExecution(test_case_id=tc2.id, status="blocked", build_version="2.0.0")
        self.db.add_all([ex1, ex2, ex3])

        cr1 = ChangeRequest(
            project_id=p1.id,
            title="Update MFA flow",
            description="Add hardware key check",
            status="completed",
            modules=[m1],
        )
        cr2 = ChangeRequest(
            project_id=p2.id,
            title="Cart tax calculation",
            description="Adjust VAT rounding",
            status="submitted",
            modules=[m3],
        )
        self.db.add_all([cr1, cr2])
        self.db.flush()

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)

        run1 = AnalysisRun(
            change_request_id=cr1.id,
            status="completed",
            created_at=yesterday,
            completed_at=yesterday,
        )
        run2 = AnalysisRun(
            change_request_id=cr2.id,
            status="failed",
            created_at=now,
            completed_at=now,
        )
        run3 = AnalysisRun(
            change_request_id=None,
            status="completed",
            created_at=yesterday - timedelta(days=2),
            completed_at=yesterday - timedelta(days=2),
        )
        self.db.add_all([run1, run2, run3])
        self.db.flush()

        rec1 = Recommendation(
            analysis_run_id=run1.id,
            test_case_id=tc1.id,
            rank=1,
            score=85.0,
            impact_level="High",
            reason="Direct module and semantic match",
            score_breakdown={"direct_module_match": 40.0, "semantic_search_match": 25.0, "related_defect_match": 20.0, "related_execution_match": 0.0},
            supporting_evidence=[],
            review_status="pending",
        )
        rec2 = Recommendation(
            analysis_run_id=run1.id,
            test_case_id=tc2.id,
            rank=2,
            score=40.0,
            impact_level="Medium",
            reason="Secondary context",
            score_breakdown={"direct_module_match": 40.0, "semantic_search_match": 0.0, "related_defect_match": 0.0, "related_execution_match": 0.0},
            supporting_evidence=[],
            review_status="pending",
        )
        self.db.add_all([rec1, rec2])
        self.db.commit()

        # Verify dashboard summary
        dash_resp = self.client.get("/dashboard/summary")
        self.assertEqual(dash_resp.status_code, 200)
        dash = dash_resp.json()
        self.assertEqual(dash["total_projects"], 2)
        self.assertEqual(dash["total_modules"], 3)
        self.assertEqual(dash["total_test_cases"], 2)
        self.assertEqual(dash["total_defects"], 1)
        self.assertEqual(dash["total_change_requests"], 2)
        self.assertEqual(dash["total_analysis_runs"], 3)
        self.assertEqual(len(dash["projects_overview"]), 2)
        self.assertEqual(dash["projects_overview"][0]["module_count"], 2)
        self.assertEqual(dash["projects_overview"][0]["test_case_count"], 1)
        self.assertEqual(
            dash["impact_level_distribution"],
            [{"label": "High", "count": 1}, {"label": "Medium", "count": 1}, {"label": "Low", "count": 0}],
        )
        self.assertEqual(
            dash["execution_status_distribution"],
            [{"label": "passed", "count": 1}, {"label": "failed", "count": 1}, {"label": "blocked", "count": 1}],
        )
        self.assertEqual(dash["recent_analysis_runs"][0]["id"], run2.id)

        # Verify GET /analysis-runs listing and filters
        list_resp = self.client.get("/analysis-runs?limit=2&offset=0")
        self.assertEqual(list_resp.status_code, 200)
        list_data = list_resp.json()
        self.assertEqual(list_data["total"], 3)
        self.assertEqual(len(list_data["items"]), 2)
        self.assertEqual(list_data["items"][0]["id"], run2.id)
        self.assertEqual(list_data["items"][0]["project_name"], "Shop Portal")
        self.assertEqual(list_data["items"][1]["id"], run1.id)
        self.assertEqual(list_data["items"][1]["total_recommendations"], 2)

        # Filter by project_id
        proj_resp = self.client.get(f"/analysis-runs?project_id={p1.id}")
        self.assertEqual(proj_resp.status_code, 200)
        self.assertEqual(proj_resp.json()["total"], 1)
        self.assertEqual(proj_resp.json()["items"][0]["id"], run1.id)

        # Filter by status
        status_resp = self.client.get("/analysis-runs?status=failed")
        self.assertEqual(status_resp.status_code, 200)
        self.assertEqual(status_resp.json()["total"], 1)
        self.assertEqual(status_resp.json()["items"][0]["id"], run2.id)

        # Filter by date_from / date_to
        today_str = date.today().isoformat()
        date_resp = self.client.get(f"/analysis-runs?date_from={today_str}&date_to={today_str}")
        self.assertEqual(date_resp.status_code, 200)
        self.assertGreaterEqual(date_resp.json()["total"], 1)

    def test_04_cors_allows_configured_dev_origin_and_blocks_wildcard(self):
        resp = self.client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.headers.get("access-control-allow-origin"),
            "http://localhost:5173",
        )
        self.assertNotEqual(resp.headers.get("access-control-allow-origin"), "*")

        disallowed = self.client.get(
            "/health",
            headers={"Origin": "http://untrusted.example.com"},
        )
        self.assertEqual(disallowed.status_code, 200)
        self.assertIsNone(disallowed.headers.get("access-control-allow-origin"))


if __name__ == "__main__":
    unittest.main()
