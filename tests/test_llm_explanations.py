import json
import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import (
    AnalysisExplanation,
    AnalysisRun,
    ChangeRequest,
    Defect,
    Module,
    Project,
    Recommendation,
    TestCase,
    TestExecution,
)
from app.rag.embeddings import CompanyEmbeddings


class TestLLMExplanationsSuite(unittest.TestCase):
    """Milestone 8 Test Suite: Grounded LLM Explanation generation, validation, persistence & endpoints."""

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

        self.llm_env = {
            "COMPANY_LLM_API_URL": "https://llm.internal.company.com/v1/chat/completions",
            "COMPANY_LLM_API_KEY": "test-llm-secret-key-abc123",
            "COMPANY_LLM_MODEL_NAME": "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "COMPANY_LLM_TEMPERATURE": "0.5",
            "COMPANY_LLM_TOP_P": "0.9",
            "COMPANY_LLM_MAX_TOKENS": "1000",
            "COMPANY_LLM_TIMEOUT": "60",
        }

        # Seed Project 1: Banking
        self.p_bank = Project(name="Banking App", description="Core banking system")
        self.db.add(self.p_bank)
        self.db.flush()

        self.m_auth = Module(
            project_id=self.p_bank.id,
            name="Authentication",
            description="Login, MFA, and JWT session validation",
        )
        self.m_transfer = Module(
            project_id=self.p_bank.id,
            name="Money Transfer",
            description="Wire & ACH settlement",
        )
        self.db.add_all([self.m_auth, self.m_transfer])
        self.db.flush()

        self.tc_login = TestCase(
            project_id=self.p_bank.id,
            title="Verify valid user login",
            steps="1. Enter username\n2. Enter password\n3. Click Login",
            expected_result="Dashboard displayed with active session",
            priority="High",
            modules=[self.m_auth],
        )
        self.tc_transfer = TestCase(
            project_id=self.p_bank.id,
            title="Block transfer on expired session",
            steps="1. Expire JWT\n2. Click Confirm Transfer",
            expected_result="HTTP 401 returned and no balance deducted",
            priority="Critical",
            modules=[self.m_auth, self.m_transfer],
        )
        self.db.add_all([self.tc_login, self.tc_transfer])
        self.db.flush()

        self.defect_auth = Defect(
            project_id=self.p_bank.id,
            module_id=self.m_auth.id,
            title="Session token expires prematurely under load",
            description="JWT token terminated early during concurrent API traffic.",
            resolution_notes="Added mutex lock around token refresh queue.",
            severity="High",
        )
        self.db.add(self.defect_auth)
        self.db.flush()

        self.exec_login = TestExecution(
            test_case_id=self.tc_login.id,
            status="failed",
            build_version="banking-v1.0",
        )
        self.db.add(self.exec_login)
        self.db.flush()

        self.cr_bank = ChangeRequest(
            project_id=self.p_bank.id,
            title="CR-BANK-001: Biometric WebAuthn MFA Step-Up",
            description="Enforce step-up WebAuthn verification before wire transfers.",
            status="submitted",
            modules=[self.m_auth],
        )
        self.db.add(self.cr_bank)
        self.db.flush()

        # Seed Project 2: E-Commerce (for cross-project isolation checks)
        self.p_ecom = Project(name="E-Commerce App", description="Retail storefront")
        self.db.add(self.p_ecom)
        self.db.flush()

        self.m_checkout = Module(
            project_id=self.p_ecom.id,
            name="Checkout",
            description="Order submission",
        )
        self.db.add(self.m_checkout)
        self.db.flush()

        self.defect_ecom = Defect(
            project_id=self.p_ecom.id,
            module_id=self.m_checkout.id,
            title="Cross-project checkout defect",
            description="Should never be leaked into Banking explanations.",
            resolution_notes="Fixed webhook queue.",
            severity="Critical",
        )
        self.db.add(self.defect_ecom)
        self.db.flush()

        # Run deterministic impact analysis via mocked retrieval (independent of LLM!)
        with patch("app.services.impact_analysis.search_project_knowledge") as mock_search:
            mock_search.return_value = [
                {
                    "source_type": "test_case",
                    "source_id": self.tc_login.id,
                    "project_id": self.p_bank.id,
                    "distance": 0.08,
                },
                {
                    "source_type": "defect",
                    "source_id": self.defect_auth.id,
                    "project_id": self.p_bank.id,
                    "distance": 0.14,
                },
                {
                    "source_type": "test_execution",
                    "source_id": self.exec_login.id,
                    "project_id": self.p_bank.id,
                    "distance": 0.19,
                },
            ]
            analyze_resp = self.client.post(
                f"/change-requests/{self.cr_bank.id}/analyze",
                json={"top_k": 5},
            )
            self.assertEqual(analyze_resp.status_code, 200)
            self.analysis_data = analyze_resp.json()

        self.run_id = self.analysis_data["analysis_run_id"]
        self.recs = self.analysis_data["recommendations"]
        self.rec_1 = next(r for r in self.recs if r["test_case_id"] == self.tc_login.id)
        self.rec_2 = next(r for r in self.recs if r["test_case_id"] == self.tc_transfer.id)

    def tearDown(self):
        self.db.close()

    def _valid_llm_payload(self, summary: str = "Grounded summary for Biometric MFA change.") -> dict:
        return {
            "overall_summary": summary,
            "risk_observations": [
                "Historical defect in Authentication shows token refresh sensitivity; this represents prior risk rather than a current defect.",
                "Earlier failed execution on build banking-v1.0 warrants login regression verification.",
            ],
            "recommendations": [
                {
                    "recommendation_id": self.rec_1["id"],
                    "test_case_id": self.tc_login.id,
                    "explanation": "Recommended due to direct Authentication module match, semantic match, historical defect, and prior execution record.",
                    "evidence_refs": [
                        {"source_type": "module", "source_id": self.m_auth.id},
                        {"source_type": "test_case", "source_id": self.tc_login.id},
                        {"source_type": "defect", "source_id": self.defect_auth.id},
                        {"source_type": "test_execution", "source_id": self.exec_login.id},
                    ],
                },
                {
                    "recommendation_id": self.rec_2["id"],
                    "test_case_id": self.tc_transfer.id,
                    "explanation": "Recommended because it covers Authentication and shares historical defect module exposure.",
                    "evidence_refs": [
                        {"source_type": "module", "source_id": self.m_auth.id},
                        {"source_type": "defect", "source_id": self.defect_auth.id},
                    ],
                },
            ],
            "limitations": [
                "The analysis does not inspect actual source-code changes.",
            ],
        }

    def _mock_llm_http_json(self, mock_post, content_str: str):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": content_str}}]
        }
        mock_post.return_value = mock_resp

    # 11. Malformed explanation JSON
    @patch("requests.post")
    def test_01_malformed_explanation_json_rejected(self, mock_post):
        malformed_outputs = [
            "Here is the JSON: {not valid json",
            '```json\n{"overall_summary": "Wrapped in markdown"}\n```',
            json.dumps(["a_list_instead_of_object"]),
            json.dumps({"overall_summary": "Missing other keys"}),
            json.dumps(
                {
                    **self._valid_llm_payload(),
                    "extra_forbidden_field": "should_fail",
                }
            ),
            json.dumps(
                {
                    **self._valid_llm_payload(),
                    "recommendations": [
                        {
                            "recommendation_id": self.rec_1["id"],
                            "test_case_id": self.tc_login.id,
                            "explanation": "Trying to override score",
                            "evidence_refs": [],
                            "score": 99.9,  # Must be rejected!
                        },
                        {
                            "recommendation_id": self.rec_2["id"],
                            "test_case_id": self.tc_transfer.id,
                            "explanation": "Valid second item",
                            "evidence_refs": [],
                        },
                    ],
                }
            ),
        ]

        with patch.dict(os.environ, self.llm_env, clear=False):
            for bad_content in malformed_outputs:
                self._mock_llm_http_json(mock_post, bad_content)
                resp = self.client.post(f"/analysis-runs/{self.run_id}/explain")
                self.assertEqual(resp.status_code, 502)

        # Ensure nothing persisted in analysis_explanations
        self.assertIsNone(
            self.db.query(AnalysisExplanation)
            .filter(AnalysisExplanation.analysis_run_id == self.run_id)
            .first()
        )

    # 12. Unknown, duplicate, and omitted recommendation IDs
    @patch("requests.post")
    def test_02_unknown_duplicate_or_omitted_recommendation_ids_rejected(self, mock_post):
        with patch.dict(os.environ, self.llm_env, clear=False):
            # Unknown recommendation_id
            payload_unknown = self._valid_llm_payload()
            payload_unknown["recommendations"][0]["recommendation_id"] = 99999
            self._mock_llm_http_json(mock_post, json.dumps(payload_unknown))
            resp = self.client.post(f"/analysis-runs/{self.run_id}/explain")
            self.assertEqual(resp.status_code, 502)
            self.assertIn("unknown recommendation_id", resp.json()["detail"].lower())

            # Omitted recommendation_id (trying to delete rec_2)
            payload_omitted = self._valid_llm_payload()
            payload_omitted["recommendations"] = [payload_omitted["recommendations"][0]]
            self._mock_llm_http_json(mock_post, json.dumps(payload_omitted))
            resp = self.client.post(f"/analysis-runs/{self.run_id}/explain")
            self.assertEqual(resp.status_code, 502)
            self.assertIn("omitted", resp.json()["detail"].lower())

            # Duplicate recommendation_id
            payload_dup = self._valid_llm_payload()
            payload_dup["recommendations"][1]["recommendation_id"] = self.rec_1["id"]
            payload_dup["recommendations"][1]["test_case_id"] = self.tc_login.id
            self._mock_llm_http_json(mock_post, json.dumps(payload_dup))
            resp = self.client.post(f"/analysis-runs/{self.run_id}/explain")
            self.assertEqual(resp.status_code, 502)
            self.assertIn("duplicate", resp.json()["detail"].lower())

    # 13. Unknown or mismatched test case IDs
    @patch("requests.post")
    def test_03_unknown_or_mismatched_test_case_ids_rejected(self, mock_post):
        with patch.dict(os.environ, self.llm_env, clear=False):
            payload = self._valid_llm_payload()
            payload["recommendations"][0]["test_case_id"] = 88888
            self._mock_llm_http_json(mock_post, json.dumps(payload))

            resp = self.client.post(f"/analysis-runs/{self.run_id}/explain")
            self.assertEqual(resp.status_code, 502)
            self.assertIn("test_case_id", resp.json()["detail"].lower())

            # Swapped test_case_id between two existing recommendations
            payload_swapped = self._valid_llm_payload()
            payload_swapped["recommendations"][0]["test_case_id"] = self.tc_transfer.id
            self._mock_llm_http_json(mock_post, json.dumps(payload_swapped))

            resp2 = self.client.post(f"/analysis-runs/{self.run_id}/explain")
            self.assertEqual(resp2.status_code, 502)

    # 14. Invented and cross-project evidence references rejected
    @patch("requests.post")
    def test_04_invented_and_cross_project_evidence_rejected(self, mock_post):
        with patch.dict(os.environ, self.llm_env, clear=False):
            # Invented defect ID
            payload_invented = self._valid_llm_payload()
            payload_invented["recommendations"][0]["evidence_refs"].append(
                {"source_type": "defect", "source_id": 9999}
            )
            self._mock_llm_http_json(mock_post, json.dumps(payload_invented))
            resp = self.client.post(f"/analysis-runs/{self.run_id}/explain")
            self.assertEqual(resp.status_code, 502)
            self.assertIn("evidence", resp.json()["detail"].lower())

            # Cross-project defect ID (E-Commerce defect!)
            payload_cross = self._valid_llm_payload()
            payload_cross["recommendations"][0]["evidence_refs"].append(
                {"source_type": "defect", "source_id": self.defect_ecom.id}
            )
            self._mock_llm_http_json(mock_post, json.dumps(payload_cross))
            resp2 = self.client.post(f"/analysis-runs/{self.run_id}/explain")
            self.assertEqual(resp2.status_code, 502)

            # Unsupported evidence source_type
            payload_type = self._valid_llm_payload()
            payload_type["recommendations"][0]["evidence_refs"].append(
                {"source_type": "source_code_commit", "source_id": 1}
            )
            self._mock_llm_http_json(mock_post, json.dumps(payload_type))
            resp3 = self.client.post(f"/analysis-runs/{self.run_id}/explain")
            self.assertEqual(resp3.status_code, 502)

    # 15 & 16. Valid grounded explanation, prompt evidence content, persistence & GET retrieval
    @patch("requests.post")
    def test_05_valid_grounded_explanation_and_persistence(self, mock_post):
        valid_payload = self._valid_llm_payload()
        self._mock_llm_http_json(mock_post, json.dumps(valid_payload))

        with patch.dict(os.environ, self.llm_env, clear=False):
            resp = self.client.post(f"/analysis-runs/{self.run_id}/explain")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["analysis_run_id"], self.run_id)
        self.assertEqual(data["model_name"], self.llm_env["COMPANY_LLM_MODEL_NAME"])
        self.assertEqual(data["overall_summary"], valid_payload["overall_summary"])
        self.assertEqual(len(data["recommendations"]), 2)
        self.assertIn("created_at", data)

        # Verify prompt sent to Company LLM contained serialized DB details & NO cross-project defect
        sent_prompt = mock_post.call_args.kwargs["json"]["messages"][0]["content"]
        self.assertIn(self.cr_bank.title, sent_prompt)
        self.assertIn(self.defect_auth.resolution_notes, sent_prompt)
        self.assertIn("banking-v1.0", sent_prompt)
        self.assertNotIn(self.defect_ecom.title, sent_prompt)
        self.assertNotIn(self.llm_env["COMPANY_LLM_API_KEY"], sent_prompt)

        # Verify persisted row in analysis_explanations
        rows = (
            self.db.query(AnalysisExplanation)
            .filter(AnalysisExplanation.analysis_run_id == self.run_id)
            .all()
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].model_name, self.llm_env["COMPANY_LLM_MODEL_NAME"])

        # Verify GET /analysis-runs/{id}/explanation returns persisted record without new LLM call
        mock_post.reset_mock()
        get_resp = self.client.get(f"/analysis-runs/{self.run_id}/explanation")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["overall_summary"], valid_payload["overall_summary"])
        mock_post.assert_not_called()

    # 17. Regeneration updates existing explanation rather than creating duplicates
    @patch("requests.post")
    def test_06_regeneration_updates_existing_explanation(self, mock_post):
        with patch.dict(os.environ, self.llm_env, clear=False):
            first_payload = self._valid_llm_payload(summary="Initial generated summary.")
            self._mock_llm_http_json(mock_post, json.dumps(first_payload))
            resp1 = self.client.post(f"/analysis-runs/{self.run_id}/explain")
            self.assertEqual(resp1.status_code, 200)

            second_payload = self._valid_llm_payload(summary="Updated regenerated summary.")
            self._mock_llm_http_json(mock_post, json.dumps(second_payload))
            resp2 = self.client.post(f"/analysis-runs/{self.run_id}/explain")
            self.assertEqual(resp2.status_code, 200)
            self.assertEqual(resp2.json()["overall_summary"], "Updated regenerated summary.")

        rows = (
            self.db.query(AnalysisExplanation)
            .filter(AnalysisExplanation.analysis_run_id == self.run_id)
            .all()
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].overall_summary, "Updated regenerated summary.")

        get_resp = self.client.get(f"/analysis-runs/{self.run_id}/explanation")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["overall_summary"], "Updated regenerated summary.")

    # 18, 19, 20. Failure & success preserve deterministic scores, ranks, evidence, and QA review status
    @patch("requests.post")
    def test_07_llm_success_and_failure_preserve_scores_ranks_and_review_status(self, mock_post):
        # Accept rec_1 and reject rec_2 before calling LLM
        r1 = self.client.patch(
            f"/recommendations/{self.rec_1['id']}/review",
            json={"review_status": "accepted"},
        )
        r2 = self.client.patch(
            f"/recommendations/{self.rec_2['id']}/review",
            json={"review_status": "rejected"},
        )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)

        before_run = self.client.get(f"/analysis-runs/{self.run_id}").json()

        with patch.dict(os.environ, self.llm_env, clear=False):
            # Failing LLM call (HTTP 500 -> 502)
            mock_500 = MagicMock(status_code=500)
            mock_500.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_500)
            mock_post.return_value = mock_500
            fail_resp = self.client.post(f"/analysis-runs/{self.run_id}/explain")
            self.assertEqual(fail_resp.status_code, 502)
            self.assertNotIn(self.llm_env["COMPANY_LLM_API_KEY"], fail_resp.text)

            after_fail_run = self.client.get(f"/analysis-runs/{self.run_id}").json()
            self.assertEqual(before_run, after_fail_run)

            # Successful LLM call
            mock_post.side_effect = None
            self._mock_llm_http_json(mock_post, json.dumps(self._valid_llm_payload()))
            ok_resp = self.client.post(f"/analysis-runs/{self.run_id}/explain")
            self.assertEqual(ok_resp.status_code, 200)

            # Subsequent failing regeneration must preserve existing explanation & recommendations
            mock_post.side_effect = requests.exceptions.Timeout("Upstream timeout")
            regen_fail_resp = self.client.post(f"/analysis-runs/{self.run_id}/explain")
            self.assertEqual(regen_fail_resp.status_code, 502)

            persisted_get = self.client.get(f"/analysis-runs/{self.run_id}/explanation")
            self.assertEqual(persisted_get.status_code, 200)
            self.assertEqual(
                persisted_get.json()["overall_summary"],
                self._valid_llm_payload()["overall_summary"],
            )

        after_ok_run = self.client.get(f"/analysis-runs/{self.run_id}").json()
        self.assertEqual(before_run, after_ok_run)

        # Explicitly check scores, ranks, impact levels, and QA review statuses
        self.assertEqual(after_ok_run["recommendations"][0]["review_status"], "accepted")
        self.assertEqual(after_ok_run["recommendations"][1]["review_status"], "rejected")
        self.assertEqual(after_ok_run["recommendations"][0]["score"], self.rec_1["score"])
        self.assertEqual(after_ok_run["recommendations"][0]["rank"], self.rec_1["rank"])
        self.assertEqual(
            after_ok_run["recommendations"][0]["impact_level"],
            self.rec_1["impact_level"],
        )

    # Error status codes: 404 (missing run / missing explanation) & 503 (unconfigured LLM)
    def test_08_endpoint_404_and_503_status_codes(self):
        # 404 when analysis run does not exist
        resp_missing_post = self.client.post("/analysis-runs/99999/explain")
        self.assertEqual(resp_missing_post.status_code, 404)

        resp_missing_get = self.client.get("/analysis-runs/99999/explanation")
        self.assertEqual(resp_missing_get.status_code, 404)

        # 404 when explanation has not yet been generated for an existing run
        resp_no_exp = self.client.get(f"/analysis-runs/{self.run_id}/explanation")
        self.assertEqual(resp_no_exp.status_code, 404)

        # 503 when LLM provider is not configured
        with patch.dict(
            os.environ,
            {
                "COMPANY_LLM_API_URL": "",
                "COMPANY_LLM_API_KEY": "",
                "COMPANY_LLM_MODEL_NAME": "",
            },
            clear=False,
        ):
            resp_503 = self.client.post(f"/analysis-runs/{self.run_id}/explain")
            self.assertEqual(resp_503.status_code, 503)

    # 21. Existing CRUD, deterministic analysis (without LLM creds), and embedding adapter stay operational
    @patch("app.services.impact_analysis.search_project_knowledge")
    def test_09_existing_crud_analysis_and_embeddings_unaffected(self, mock_search):
        mock_search.return_value = []

        # Deterministic analysis succeeds even with blank LLM credentials
        with patch.dict(
            os.environ,
            {
                "COMPANY_LLM_API_URL": "",
                "COMPANY_LLM_API_KEY": "",
                "COMPANY_LLM_MODEL_NAME": "",
            },
            clear=False,
        ):
            analyze_resp = self.client.post(f"/change-requests/{self.cr_bank.id}/analyze")
            self.assertEqual(analyze_resp.status_code, 200)
            self.assertEqual(analyze_resp.json()["status"], "completed")

        # CRUD endpoints remain healthy
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/projects/").status_code, 200)
        self.assertEqual(self.client.get("/test-cases/").status_code, 200)
        self.assertEqual(self.client.get("/defects/").status_code, 200)
        self.assertEqual(self.client.get("/test-executions/").status_code, 200)
        self.assertEqual(self.client.get("/change-requests/").status_code, 200)

        # CompanyEmbeddings adapter remains intact
        emb = CompanyEmbeddings(
            api_url="https://emb.internal.company.com/v2/text/embeddings",
            api_key="emb-key-123456",
            dimensions=736,
        )
        self.assertTrue(emb.is_configured())


if __name__ == "__main__":
    unittest.main()
