from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock, patch

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
from app.rag.embeddings import CompanyEmbeddingError, CompanyEmbeddingNotConfiguredError
from app.services.recommendation_engine import (
    SCORING_WEIGHTS,
    build_recommendation_candidates,
    determine_impact_level,
)


class TestImpactAnalysisSuite(unittest.TestCase):
    """Milestone 7 Test Suite: Comprehensive verification of Impact Analysis & Recommendations."""

    @classmethod
    def setUpClass(cls):
        # Create an in-memory SQLite engine shared across threads for TestClient
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

    def setUp(self):
        # Seed fresh records for each test
        self.db = self.TestingSessionLocal()

        # Clean tables
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

        # Seed Project 1: Banking
        self.p_bank = Project(name="Banking App", description="Core banking system")
        self.db.add(self.p_bank)
        self.db.flush()

        self.m_auth = Module(project_id=self.p_bank.id, name="Authentication", description="Auth & MFA")
        self.m_trans = Module(project_id=self.p_bank.id, name="Money Transfer", description="Wire & ACH")
        self.db.add_all([self.m_auth, self.m_trans])
        self.db.flush()

        self.tc_login = TestCase(
            project_id=self.p_bank.id,
            title="Verify valid user login",
            steps="1. Enter user\n2. Enter pass\n3. Click Login",
            expected_result="Dashboard displayed",
            priority="High",
            modules=[self.m_auth],
        )
        self.tc_bad_login = TestCase(
            project_id=self.p_bank.id,
            title="Reject login with bad password",
            steps="1. Enter user\n2. Enter bad pass\n3. Click Login",
            expected_result="401 Unauthorized",
            priority="High",
            modules=[self.m_auth],
        )
        self.tc_transfer = TestCase(
            project_id=self.p_bank.id,
            title="Execute wire transfer",
            steps="1. Select account\n2. Enter amount\n3. Confirm",
            expected_result="Transfer queued",
            priority="Medium",
            modules=[self.m_trans],
        )
        self.db.add_all([self.tc_login, self.tc_bad_login, self.tc_transfer])
        self.db.flush()

        self.defect_token = Defect(
            project_id=self.p_bank.id,
            module_id=self.m_auth.id,
            title="Session token expires prematurely under load",
            description="JWT session drops after 2 minutes",
            severity="High",
        )
        self.db.add(self.defect_token)
        self.db.flush()

        self.exec_login = TestExecution(
            test_case_id=self.tc_login.id,
            status="passed",
            build_version="v1.0.0",
        )
        self.db.add(self.exec_login)
        self.db.flush()

        self.cr_bank = ChangeRequest(
            project_id=self.p_bank.id,
            title="CR-BANK-001: Biometric WebAuthn MFA Step-Up",
            description="Add FIDO2 biometric authentication for high-risk operations",
            status="submitted",
            modules=[self.m_auth],
        )
        self.db.add(self.cr_bank)
        self.db.flush()

        # Seed Project 2: E-Commerce
        self.p_ecom = Project(name="E-Commerce App", description="Retail marketplace")
        self.db.add(self.p_ecom)
        self.db.flush()

        self.m_catalog = Module(project_id=self.p_ecom.id, name="Catalog", description="Product listing")
        self.m_checkout = Module(project_id=self.p_ecom.id, name="Checkout", description="Cart & payment")
        self.db.add_all([self.m_catalog, self.m_checkout])
        self.db.flush()

        self.tc_search = TestCase(
            project_id=self.p_ecom.id,
            title="Search catalog by keyword",
            steps="1. Type query\n2. Click search",
            expected_result="Matching products shown",
            priority="Medium",
            modules=[self.m_catalog],
        )
        self.tc_checkout = TestCase(
            project_id=self.p_ecom.id,
            title="Complete standard checkout",
            steps="1. Review cart\n2. Enter card\n3. Submit",
            expected_result="Order confirmation",
            priority="High",
            modules=[self.m_checkout],
        )
        self.db.add_all([self.tc_search, self.tc_checkout])
        self.db.flush()

        self.cr_ecom = ChangeRequest(
            project_id=self.p_ecom.id,
            title="CR-ECOM-001: Support Apple Pay",
            description="Integrate Apple Pay one-touch checkout",
            status="submitted",
            modules=[self.m_checkout],
        )
        self.db.add(self.cr_ecom)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    # 1. Analysis of an existing Banking change request
    @patch("app.services.impact_analysis.search_project_knowledge")
    def test_01_analyze_banking_change_request(self, mock_search):
        mock_search.return_value = [
            {
                "source_type": "test_case",
                "source_id": self.tc_login.id,
                "project_id": self.p_bank.id,
                "distance": 0.12,
            }
        ]

        response = self.client.post(
            f"/change-requests/{self.cr_bank.id}/analyze",
            json={"top_k": 5},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["change_request_id"], self.cr_bank.id)
        self.assertEqual(data["project_id"], self.p_bank.id)
        self.assertEqual(data["status"], "completed")
        self.assertGreater(data["total_recommendations"], 0)

    # 2. Analysis of an E-Commerce change request
    @patch("app.services.impact_analysis.search_project_knowledge")
    def test_02_analyze_ecommerce_change_request(self, mock_search):
        mock_search.return_value = [
            {
                "source_type": "test_case",
                "source_id": self.tc_checkout.id,
                "project_id": self.p_ecom.id,
                "distance": 0.15,
            }
        ]

        response = self.client.post(
            f"/change-requests/{self.cr_ecom.id}/analyze",
            json={"top_k": 5},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["change_request_id"], self.cr_ecom.id)
        self.assertEqual(data["project_id"], self.p_ecom.id)
        self.assertEqual(data["recommendations"][0]["test_case_id"], self.tc_checkout.id)

    # 3. Candidate generation through direct module relationships
    def test_03_candidate_generation_direct_module(self):
        # Without any RAG retrieval, candidate generation should discover tc_login and tc_bad_login via m_auth
        candidates = build_recommendation_candidates(
            change_request=self.cr_bank,
            retrieved_records=[],
            db=self.db,
        )
        cand_tc_ids = [c["test_case_id"] for c in candidates]
        self.assertIn(self.tc_login.id, cand_tc_ids)
        self.assertIn(self.tc_bad_login.id, cand_tc_ids)
        self.assertNotIn(self.tc_transfer.id, cand_tc_ids)

        for c in candidates:
            self.assertEqual(c["score_breakdown"]["direct_module_match"], 40.0)

    # 4. Candidate generation from retrieved test-case documents
    def test_04_candidate_generation_retrieved_test_case(self):
        retrieved = [
            {
                "source_type": "test_case",
                "source_id": self.tc_transfer.id,  # not in affected module
                "distance": 0.08,
            }
        ]
        candidates = build_recommendation_candidates(
            change_request=self.cr_bank,
            retrieved_records=retrieved,
            db=self.db,
        )
        transfer_cand = next(c for c in candidates if c["test_case_id"] == self.tc_transfer.id)
        self.assertEqual(transfer_cand["score_breakdown"]["semantic_search_match"], 25.0)
        self.assertEqual(transfer_cand["score_breakdown"]["direct_module_match"], 0.0)

    # 5. Candidate generation from retrieved defects
    def test_05_candidate_generation_retrieved_defects(self):
        retrieved = [
            {
                "source_type": "defect",
                "source_id": self.defect_token.id,  # belongs to Authentication module
                "distance": 0.22,
            }
        ]
        candidates = build_recommendation_candidates(
            change_request=self.cr_bank,
            retrieved_records=retrieved,
            db=self.db,
        )
        login_cand = next(c for c in candidates if c["test_case_id"] == self.tc_login.id)
        self.assertEqual(login_cand["score_breakdown"]["related_defect_match"], 20.0)
        self.assertTrue(any(ev["source_type"] == "defect" for ev in login_cand["supporting_evidence"]))

    # 6. Candidate generation from retrieved execution records
    def test_06_candidate_generation_retrieved_executions(self):
        retrieved = [
            {
                "source_type": "test_execution",
                "source_id": self.exec_login.id,  # executed tc_login
                "distance": 0.19,
            }
        ]
        candidates = build_recommendation_candidates(
            change_request=self.cr_bank,
            retrieved_records=retrieved,
            db=self.db,
        )
        login_cand = next(c for c in candidates if c["test_case_id"] == self.tc_login.id)
        self.assertEqual(login_cand["score_breakdown"]["related_execution_match"], 15.0)

    # 7. Duplicate candidate consolidation
    def test_07_duplicate_candidate_consolidation(self):
        # tc_login matches direct module, test case retrieval, defect module, and execution
        retrieved = [
            {"source_type": "test_case", "source_id": self.tc_login.id, "distance": 0.05},
            {"source_type": "defect", "source_id": self.defect_token.id, "distance": 0.12},
            {"source_type": "test_execution", "source_id": self.exec_login.id, "distance": 0.20},
        ]
        candidates = build_recommendation_candidates(
            change_request=self.cr_bank,
            retrieved_records=retrieved,
            db=self.db,
        )
        tc_login_entries = [c for c in candidates if c["test_case_id"] == self.tc_login.id]
        self.assertEqual(len(tc_login_entries), 1, "tc_login must appear exactly once")

    # 8. Cross-project candidate exclusion
    def test_08_cross_project_candidate_exclusion(self):
        # Simulate RAG mistakenly returning an E-Commerce record during a Banking query
        retrieved = [
            {"source_type": "test_case", "source_id": self.tc_search.id, "distance": 0.02},  # E-Commerce test case!
        ]
        candidates = build_recommendation_candidates(
            change_request=self.cr_bank,
            retrieved_records=retrieved,
            db=self.db,
        )
        cand_ids = [c["test_case_id"] for c in candidates]
        self.assertNotIn(self.tc_search.id, cand_ids, "E-Commerce test cases must NEVER appear in Banking recommendations")

    # 9. Correct score calculation
    def test_09_correct_score_calculation(self):
        # All 4 signals present for tc_login: 40 + 25 + 20 + 15 = 100
        retrieved = [
            {"source_type": "test_case", "source_id": self.tc_login.id, "distance": 0.05},
            {"source_type": "defect", "source_id": self.defect_token.id, "distance": 0.12},
            {"source_type": "test_execution", "source_id": self.exec_login.id, "distance": 0.20},
        ]
        candidates = build_recommendation_candidates(
            change_request=self.cr_bank,
            retrieved_records=retrieved,
            db=self.db,
        )
        login_cand = next(c for c in candidates if c["test_case_id"] == self.tc_login.id)
        self.assertEqual(login_cand["score"], 100.0)
        self.assertEqual(login_cand["impact_level"], "High")

        # tc_bad_login only has direct module match (40) and defect match (20) = 60
        bad_login_cand = next(c for c in candidates if c["test_case_id"] == self.tc_bad_login.id)
        self.assertEqual(bad_login_cand["score"], 60.0)
        self.assertEqual(bad_login_cand["impact_level"], "Medium")

    # 10. Correct ranking and tie-breaking
    def test_10_correct_ranking_and_tie_breaking(self):
        retrieved = [
            {"source_type": "test_case", "source_id": self.tc_login.id, "distance": 0.05},
        ]
        candidates = build_recommendation_candidates(
            change_request=self.cr_bank,
            retrieved_records=retrieved,
            db=self.db,
        )
        # tc_login has score 40+25=65, tc_bad_login has score 40
        self.assertEqual(candidates[0]["test_case_id"], self.tc_login.id)
        self.assertEqual(candidates[0]["rank"], 1)
        self.assertEqual(candidates[1]["test_case_id"], self.tc_bad_login.id)
        self.assertEqual(candidates[1]["rank"], 2)

    # 11. Evidence traceability
    def test_11_evidence_traceability(self):
        retrieved = [
            {"source_type": "test_case", "source_id": self.tc_login.id, "distance": 0.05},
        ]
        candidates = build_recommendation_candidates(
            change_request=self.cr_bank,
            retrieved_records=retrieved,
            db=self.db,
        )
        login_cand = candidates[0]
        evidence_types = {e["source_type"] for e in login_cand["supporting_evidence"]}
        self.assertIn("module", evidence_types)
        self.assertIn("test_case", evidence_types)

    # 12. Analysis run persistence
    @patch("app.services.impact_analysis.search_project_knowledge")
    def test_12_analysis_run_persistence(self, mock_search):
        mock_search.return_value = []
        resp = self.client.post(f"/change-requests/{self.cr_bank.id}/analyze")
        self.assertEqual(resp.status_code, 200)
        run_id = resp.json()["analysis_run_id"]

        run_in_db = self.db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        self.assertIsNotNone(run_in_db)
        self.assertEqual(run_in_db.status, "completed")
        self.assertIsNotNone(run_in_db.completed_at)

    # 13. Retrieval of persisted analysis results
    @patch("app.services.impact_analysis.search_project_knowledge")
    def test_13_get_persisted_analysis_run(self, mock_search):
        mock_search.return_value = []
        resp = self.client.post(f"/change-requests/{self.cr_bank.id}/analyze")
        run_id = resp.json()["analysis_run_id"]

        get_resp = self.client.get(f"/analysis-runs/{run_id}")
        self.assertEqual(get_resp.status_code, 200)
        data = get_resp.json()
        self.assertEqual(data["id"], run_id)
        self.assertEqual(data["status"], "completed")
        self.assertGreaterEqual(len(data["recommendations"]), 1)

    # 14. Accepting a recommendation
    @patch("app.services.impact_analysis.search_project_knowledge")
    def test_14_accept_recommendation(self, mock_search):
        mock_search.return_value = []
        resp = self.client.post(f"/change-requests/{self.cr_bank.id}/analyze")
        rec_id = resp.json()["recommendations"][0]["id"]

        patch_resp = self.client.patch(
            f"/recommendations/{rec_id}/review",
            json={"review_status": "accepted"},
        )
        self.assertEqual(patch_resp.status_code, 200)
        self.assertEqual(patch_resp.json()["review_status"], "accepted")

        rec_in_db = self.db.query(Recommendation).filter(Recommendation.id == rec_id).first()
        self.assertEqual(rec_in_db.review_status, "accepted")

    # 15. Rejecting a recommendation
    @patch("app.services.impact_analysis.search_project_knowledge")
    def test_15_reject_recommendation(self, mock_search):
        mock_search.return_value = []
        resp = self.client.post(f"/change-requests/{self.cr_bank.id}/analyze")
        rec_id = resp.json()["recommendations"][0]["id"]

        patch_resp = self.client.patch(
            f"/recommendations/{rec_id}/review",
            json={"review_status": "rejected"},
        )
        self.assertEqual(patch_resp.status_code, 200)
        self.assertEqual(patch_resp.json()["review_status"], "rejected")

    # 16. Invalid review status handling
    def test_16_invalid_review_status_handling(self):
        # Non-existent or invalid status
        patch_resp = self.client.patch(
            "/recommendations/1/review",
            json={"review_status": "maybe_consider"},
        )
        self.assertEqual(patch_resp.status_code, 422)

    # 17. Missing change request handling
    def test_17_missing_change_request_handling(self):
        resp = self.client.post("/change-requests/9999/analyze")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())

    # 18. Missing analysis run handling
    def test_18_missing_analysis_run_handling(self):
        resp = self.client.get("/analysis-runs/9999")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())

    # 19. Embedding API failure handling
    @patch("app.services.impact_analysis.search_project_knowledge")
    def test_19_embedding_api_failure_handling(self, mock_search):
        mock_search.side_effect = CompanyEmbeddingError("Embedding API returned HTTP 500")

        resp = self.client.post(f"/change-requests/{self.cr_bank.id}/analyze")
        self.assertEqual(resp.status_code, 502)
        self.assertIn("Embedding provider error", resp.json()["detail"])

        # Check that analysis run was recorded as failed
        failed_run = (
            self.db.query(AnalysisRun)
            .filter(AnalysisRun.change_request_id == self.cr_bank.id)
            .order_by(AnalysisRun.id.desc())
            .first()
        )
        self.assertIsNotNone(failed_run)
        self.assertEqual(failed_run.status, "failed")

    # 20. Preservation of all existing endpoints
    def test_20_preservation_of_existing_endpoints(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/projects/").status_code, 200)
        self.assertEqual(self.client.get("/modules/").status_code, 404)  # Module listing requires project ID
        self.assertEqual(self.client.get(f"/projects/{self.p_bank.id}/modules").status_code, 200)
        self.assertEqual(self.client.get("/test-cases/").status_code, 200)
        self.assertEqual(self.client.get("/defects/").status_code, 200)
        self.assertEqual(self.client.get("/test-executions/").status_code, 200)
        self.assertEqual(self.client.get("/change-requests/").status_code, 200)


if __name__ == "__main__":
    unittest.main()

