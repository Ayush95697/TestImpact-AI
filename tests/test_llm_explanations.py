from datetime import datetime, timezone
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
from app.llm.explanation_service import prepare_batch_explanation_contexts
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

    def _create_eight_rec_run(self):
        """Seeds a completed analysis run with 8 ranked recommendations and varied evidence."""
        test_cases = []
        executions = []
        for idx in range(1, 9):
            tc = TestCase(
                project_id=self.p_bank.id,
                title=f"Banking Regression TC-{idx}",
                steps=f"1. Step A for TC-{idx}\n2. Step B for TC-{idx}",
                expected_result=f"Expected outcome {idx}",
                priority="High" if idx <= 3 else ("Medium" if idx <= 6 else "Low"),
                modules=[self.m_auth] if idx <= 6 else [self.m_transfer],
            )
            self.db.add(tc)
            test_cases.append(tc)
        self.db.flush()

        for idx, tc in enumerate(test_cases[:3], start=1):
            ex = TestExecution(
                test_case_id=tc.id,
                status="failed",
                build_version=f"banking-v2.{idx}",
            )
            self.db.add(ex)
            executions.append(ex)
        self.db.flush()

        run = AnalysisRun(
            change_request_id=self.cr_bank.id,
            status="completed",
            completed_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        self.db.flush()

        recs = []
        review_cycle = ["accepted", "rejected", "pending"]
        for rank in range(1, 9):
            tc = test_cases[rank - 1]
            if rank <= 3:
                score, level = 100.0 - (rank - 1) * 10.0, "High"
                evidence = [
                    {
                        "source_type": "module",
                        "source_id": self.m_auth.id,
                        "title": f"Affected Module: {self.m_auth.name}",
                    },
                    {
                        "source_type": "test_case",
                        "source_id": tc.id,
                        "title": tc.title,
                    },
                    {
                        "source_type": "defect",
                        "source_id": self.defect_auth.id,
                        "title": self.defect_auth.title,
                    },
                    {
                        "source_type": "test_execution",
                        "source_id": executions[rank - 1].id,
                        "title": f"Execution (failed) - {tc.title}",
                    },
                ]
            elif rank <= 6:
                score, level = 40.0, "Medium"
                evidence = [
                    {
                        "source_type": "module",
                        "source_id": self.m_auth.id,
                        "title": f"Affected Module: {self.m_auth.name}",
                    }
                ]
            else:
                score, level = 20.0, "Low"
                evidence = [
                    {
                        "source_type": "defect",
                        "source_id": self.defect_auth.id,
                        "title": self.defect_auth.title,
                    }
                ]

            rec = Recommendation(
                analysis_run_id=run.id,
                test_case_id=tc.id,
                rank=rank,
                score=score,
                impact_level=level,
                reason=f"Deterministic reason for rank {rank}",
                score_breakdown={"module_match": 40.0 if rank <= 6 else 0.0},
                supporting_evidence=evidence,
                review_status=review_cycle[(rank - 1) % 3],
            )
            self.db.add(rec)
            recs.append(rec)

        self.db.commit()
        for rec in recs:
            self.db.refresh(rec)
        return run, recs

    def _build_batch_response(self, batch_recs, summary="Batch summary", reverse_items=False):
        items = list(reversed(batch_recs)) if reverse_items else list(batch_recs)
        rec_payloads = []
        for rec in items:
            first_ev = rec.supporting_evidence[0]
            rec_payloads.append(
                {
                    "recommendation_id": rec.id,
                    "test_case_id": rec.test_case_id,
                    "explanation": f"Grounded explanation for recommendation {rec.id} (TC {rec.test_case_id}).",
                    "evidence_refs": [
                        {
                            "source_type": first_ev["source_type"],
                            "source_id": first_ev["source_id"],
                        }
                    ],
                }
            )
        payload = {
            "overall_summary": summary,
            "risk_observations": [
                f"Historical risk noted for batch {[r.id for r in batch_recs]}."
            ],
            "recommendations": rec_payloads,
            "limitations": [
                "The analysis does not inspect actual source-code changes."
            ],
        }
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload)}}],
            "usage": {"input_tokens": 900, "output_tokens": 320},
        }
        return mock_resp

    # Step 9 #1, #2, #3, #13, #14, #15: Eight recommendations across batches, configurable batch size, ordering, scores & reviews intact
    @patch("requests.post")
    def test_10_eight_recommendations_batched_preserving_order_scores_and_reviews(self, mock_post):
        run, recs = self._create_eight_rec_run()
        before_run = self.client.get(f"/analysis-runs/{run.id}").json()

        # batch_size=3 -> [3, 3, 2]; intentionally reverse items in Batch 2 to verify rank restoration
        mock_post.side_effect = [
            self._build_batch_response(recs[0:3], summary="Batch 1 high priority tests."),
            self._build_batch_response(recs[3:6], summary="Batch 2 medium priority tests.", reverse_items=True),
            self._build_batch_response(recs[6:8], summary="Batch 3 defect-linked tests."),
        ]

        with patch.dict(os.environ, {**self.llm_env, "COMPANY_LLM_BATCH_SIZE": "3"}, clear=False):
            resp = self.client.post(f"/analysis-runs/{run.id}/explain")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_post.call_count, 3)

        # Verify each batch prompt only included its own batch recommendations
        prompt_b1 = mock_post.call_args_list[0].kwargs["json"]["messages"][0]["content"]
        prompt_b2 = mock_post.call_args_list[1].kwargs["json"]["messages"][0]["content"]
        prompt_b3 = mock_post.call_args_list[2].kwargs["json"]["messages"][0]["content"]

        self.assertIn(f'"recommendation_id":{recs[0].id}', prompt_b1)
        self.assertNotIn(f'"recommendation_id":{recs[4].id}', prompt_b1)
        self.assertIn(f'"recommendation_id":{recs[4].id}', prompt_b2)
        self.assertNotIn(f'"recommendation_id":{recs[0].id}', prompt_b2)
        self.assertIn(f'"recommendation_id":{recs[7].id}', prompt_b3)
        self.assertNotIn(f'"recommendation_id":{recs[0].id}', prompt_b3)
        for p in (prompt_b1, prompt_b2, prompt_b3):
            self.assertNotIn(self.llm_env["COMPANY_LLM_API_KEY"], p)
            self.assertIn(self.cr_bank.title, p)

        data = resp.json()
        returned_ids = [item["recommendation_id"] for item in data["recommendations"]]
        expected_ids = [rec.id for rec in recs]
        self.assertEqual(len(returned_ids), 8)
        self.assertEqual(returned_ids, expected_ids)
        self.assertEqual(len(set(returned_ids)), 8)

        # Verify scores, ranks, impact levels, evidence, and mixed QA review statuses unchanged
        after_run = self.client.get(f"/analysis-runs/{run.id}").json()
        self.assertEqual(before_run, after_run)

        # Verify GET retrieves full 8-item explanation without new LLM calls
        mock_post.reset_mock()
        get_resp = self.client.get(f"/analysis-runs/{run.id}/explanation")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual([r["recommendation_id"] for r in get_resp.json()["recommendations"]], expected_ids)
        mock_post.assert_not_called()

        # Regenerate with configurable COMPANY_LLM_BATCH_SIZE=2 (4 batches of 2) and verify single persisted record updated
        mock_post.side_effect = [
            self._build_batch_response(recs[0:2], summary="Regen batch 1."),
            self._build_batch_response(recs[2:4], summary="Regen batch 2."),
            self._build_batch_response(recs[4:6], summary="Regen batch 3."),
            self._build_batch_response(recs[6:8], summary="Regen batch 4."),
        ]
        with patch.dict(os.environ, {**self.llm_env, "COMPANY_LLM_BATCH_SIZE": "2"}, clear=False):
            regen_resp = self.client.post(f"/analysis-runs/{run.id}/explain")
        self.assertEqual(regen_resp.status_code, 200)
        self.assertEqual(mock_post.call_count, 4)
        self.assertIn("Regen batch 1.", regen_resp.json()["overall_summary"])
        self.assertEqual(
            [r["recommendation_id"] for r in regen_resp.json()["recommendations"]],
            expected_ids,
        )
        rows = (
            self.db.query(AnalysisExplanation)
            .filter(AnalysisExplanation.analysis_run_id == run.id)
            .all()
        )
        self.assertEqual(len(rows), 1)

    # Step 9 #6, #11, #13: Mid-batch failure does not persist partial explanation & preserves prior explanation / run
    @patch("requests.post")
    def test_11_batch_failure_prevents_partial_persistence_and_cross_batch_ids(self, mock_post):
        run, recs = self._create_eight_rec_run()
        before_run = self.client.get(f"/analysis-runs/{run.id}").json()

        # Batch 1 succeeds, Batch 2 fails with HTTP 500
        mock_500 = MagicMock(status_code=500)
        mock_500.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_500)
        mock_post.side_effect = [
            self._build_batch_response(recs[0:3], summary="Batch 1 ok"),
            mock_500,
        ]
        with patch.dict(os.environ, {**self.llm_env, "COMPANY_LLM_BATCH_SIZE": "3"}, clear=False):
            fail_resp = self.client.post(f"/analysis-runs/{run.id}/explain")

        self.assertEqual(fail_resp.status_code, 502)
        self.assertEqual(self.client.get(f"/analysis-runs/{run.id}/explanation").status_code, 404)
        self.assertEqual(self.client.get(f"/analysis-runs/{run.id}").json(), before_run)

        # Cross-batch ID injection: Batch 2 returns an ID from Batch 1 instead of its own ID
        bad_batch_2 = self._build_batch_response([recs[0], recs[4], recs[5]], summary="Injected wrong batch ID")
        mock_post.side_effect = [
            self._build_batch_response(recs[0:3], summary="Batch 1 ok"),
            bad_batch_2,
        ]
        with patch.dict(os.environ, {**self.llm_env, "COMPANY_LLM_BATCH_SIZE": "3"}, clear=False):
            bad_id_resp = self.client.post(f"/analysis-runs/{run.id}/explain")

        self.assertEqual(bad_id_resp.status_code, 502)
        self.assertIn("unknown recommendation_id", bad_id_resp.json()["detail"].lower())
        self.assertEqual(self.client.get(f"/analysis-runs/{run.id}/explanation").status_code, 404)

        # Persist a complete 8-rec explanation, then verify mid-batch failure during regeneration keeps prior explanation intact
        mock_post.side_effect = [
            self._build_batch_response(recs[0:3], summary="Baseline batch 1"),
            self._build_batch_response(recs[3:6], summary="Baseline batch 2"),
            self._build_batch_response(recs[6:8], summary="Baseline batch 3"),
        ]
        with patch.dict(os.environ, {**self.llm_env, "COMPANY_LLM_BATCH_SIZE": "3"}, clear=False):
            ok_resp = self.client.post(f"/analysis-runs/{run.id}/explain")
        self.assertEqual(ok_resp.status_code, 200)
        baseline_summary = ok_resp.json()["overall_summary"]

        mock_post.side_effect = [
            self._build_batch_response(recs[0:3], summary="Failed regen batch 1"),
            mock_500,
        ]
        with patch.dict(os.environ, {**self.llm_env, "COMPANY_LLM_BATCH_SIZE": "3"}, clear=False):
            regen_fail_resp = self.client.post(f"/analysis-runs/{run.id}/explain")
        self.assertEqual(regen_fail_resp.status_code, 502)
        preserved = self.client.get(f"/analysis-runs/{run.id}/explanation")
        self.assertEqual(preserved.status_code, 200)
        self.assertEqual(preserved.json()["overall_summary"], baseline_summary)

    # Step 9 #10: Truncation metadata (finish_reason="length" and output_tokens >= max_tokens) handled clearly
    @patch("requests.post")
    def test_12_truncation_diagnostics_reported_clearly(self, mock_post):
        run, _ = self._create_eight_rec_run()

        # Truncated JSON with finish_reason="length"
        mock_len = MagicMock(status_code=200)
        mock_len.json.return_value = {
            "choices": [
                {"finish_reason": "length", "message": {"content": '{"overall_summary": "truncated mid json'}}
            ],
            "usage": {"input_tokens": 1100, "output_tokens": 1000},
        }
        mock_post.return_value = mock_len

        with patch.dict(os.environ, {**self.llm_env, "COMPANY_LLM_BATCH_SIZE": "3"}, clear=False):
            resp1 = self.client.post(f"/analysis-runs/{run.id}/explain")
        self.assertEqual(resp1.status_code, 502)
        detail1 = resp1.json()["detail"].lower()
        self.assertIn("truncated", detail1)
        self.assertIn("length", detail1)
        self.assertIn("1000", detail1)
        self.assertNotIn(self.llm_env["COMPANY_LLM_API_KEY"], resp1.text)

        # Gateway reports finish_reason="stop" even when output_tokens hits max_tokens
        mock_cap = MagicMock(status_code=200)
        mock_cap.json.return_value = {
            "choices": [
                {"finish_reason": "stop", "message": {"content": '{"overall_summary": "cut at 1000'}}
            ],
            "usage": {"input_tokens": 1100, "output_tokens": 1000},
        }
        mock_post.return_value = mock_cap

        with patch.dict(os.environ, {**self.llm_env, "COMPANY_LLM_BATCH_SIZE": "3"}, clear=False):
            resp2 = self.client.post(f"/analysis-runs/{run.id}/explain")
        self.assertEqual(resp2.status_code, 502)
        self.assertIn("truncated", resp2.json()["detail"].lower())
        self.assertIn("output_tokens=1000", resp2.json()["detail"])

    # Step 9 #4, #12: Targeted retry recovers cleanly when missing ID is explained on retry, and rejects persistent omission
    @patch("requests.post")
    def test_13_missing_recommendation_retry_recovery_and_failure(self, mock_post):
        run, recs = self._create_eight_rec_run()
        # Use batch_size=3 -> Batch 1 has recs[0:3]; Batch 1 attempt 1 omits recs[2], retry recovers recs[2]!
        partial_b1 = self._build_batch_response(recs[0:2], summary="Partial batch 1")
        recovery_b1 = self._build_batch_response([recs[2]], summary="Recovered rec 3")
        ok_b2 = self._build_batch_response(recs[3:6], summary="Batch 2 ok")
        ok_b3 = self._build_batch_response(recs[6:8], summary="Batch 3 ok")

        mock_post.side_effect = [partial_b1, recovery_b1, ok_b2, ok_b3]
        with patch.dict(os.environ, {**self.llm_env, "COMPANY_LLM_BATCH_SIZE": "3"}, clear=False):
            resp = self.client.post(f"/analysis-runs/{run.id}/explain")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_post.call_count, 4)
        self.assertEqual(
            [r["recommendation_id"] for r in resp.json()["recommendations"]],
            [r.id for r in recs],
        )

        # Retry prompt specifically targeted only the missing recommendation ID
        retry_prompt = mock_post.call_args_list[1].kwargs["json"]["messages"][0]["content"]
        self.assertIn(f'"recommendation_id":{recs[2].id}', retry_prompt)
        self.assertNotIn(f'"recommendation_id":{recs[0].id}', retry_prompt)

        # Unrecoverable omission on retry still fails strictly without saving
        run2, recs2 = self._create_eight_rec_run()
        mock_post.side_effect = [
            self._build_batch_response(recs2[0:2], summary="Partial batch 1"),
            self._build_batch_response(recs2[0:1], summary="Wrong retry response"),
        ]
        with patch.dict(os.environ, {**self.llm_env, "COMPANY_LLM_BATCH_SIZE": "3"}, clear=False):
            fail_resp = self.client.post(f"/analysis-runs/{run2.id}/explain")
        self.assertEqual(fail_resp.status_code, 502)
        self.assertIn("omitted", fail_resp.json()["detail"].lower())
        self.assertEqual(self.client.get(f"/analysis-runs/{run2.id}/explanation").status_code, 404)

    # Verify prepare_batch_explanation_contexts isolation and scoped evidence per batch
    def test_14_prepare_batch_explanation_contexts_scoping(self):
        run, recs = self._create_eight_rec_run()
        self.db.refresh(run)
        prepared = prepare_batch_explanation_contexts(analysis_run=run, db=self.db, batch_size=3)

        self.assertEqual(len(prepared["batches"]), 3)
        self.assertEqual([len(b["recommendations"]) for b in prepared["batches"]], [3, 3, 2])
        # Batch 2 only references module evidence -> supporting evidence must exclude executions/defects
        b2_evidence = json.loads(prepared["batches"][1]["prompt_inputs"]["supporting_evidence_context_json"])
        self.assertTrue(all(ev["source_type"] == "module" for ev in b2_evidence))
        # Batch 3 only references defect evidence -> supporting evidence must exclude test_cases/executions
        b3_evidence = json.loads(prepared["batches"][2]["prompt_inputs"]["supporting_evidence_context_json"])
        self.assertTrue(all(ev["source_type"] == "defect" for ev in b3_evidence))


if __name__ == "__main__":
    unittest.main()
