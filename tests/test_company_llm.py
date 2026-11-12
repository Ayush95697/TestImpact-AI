import os
import unittest
from unittest.mock import MagicMock, patch
from langchain_core.prompts import PromptTemplate
import requests

from app.llm.config import get_llm_settings
from app.llm.provider import (
    CompanyLLM,
    CompanyLLMError,
    CompanyLLMNotConfiguredError,
    CompanyLLMResponseError,
    get_llm_model,
)


class TestCompanyLLM(unittest.TestCase):
    """Unit test suite for CompanyLLM LangChain adapter and config with mocked HTTP calls."""

    def setUp(self):
        self.endpoint_url = "https://llm.internal.company.com/v1/chat/completions"
        self.secret_key = "super-secret-llm-key-998877"
        self.model_name = "meta-llama/Meta-Llama-3.1-8B-Instruct"
        self.llm = CompanyLLM(
            model=self.model_name,
            endpoint_url=self.endpoint_url,
            api_key=self.secret_key,
            temperature=0.5,
            top_p=0.9,
            max_tokens=1000,
            timeout=60,
        )

    # 1. Successful LLM request & 3. Correct extraction of choices[0].message.content
    @patch("requests.post")
    def test_01_successful_llm_request_and_content_extraction(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '{"overall_summary": "Grounded explanation text."}'
                    }
                }
            ]
        }
        mock_post.return_value = mock_response

        result = self.llm.invoke("Explain recommendation #1")
        self.assertEqual(result, '{"overall_summary": "Grounded explanation text."}')
        mock_post.assert_called_once()

    # 2. Correct API headers and payload (without and with stop sequences)
    @patch("requests.post")
    def test_02_correct_api_headers_and_payload(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Generated response"}}]
        }
        mock_post.return_value = mock_response

        # Without stop
        self.llm.invoke("PROMPT_ONE")
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(mock_post.call_args.args[0], self.endpoint_url)
        self.assertEqual(
            call_kwargs["headers"],
            {
                "Content-Type": "application/json",
                "X-API-KEY": self.secret_key,
            },
        )
        self.assertEqual(
            call_kwargs["json"],
            {
                "model": self.model_name,
                "messages": [{"role": "user", "content": "PROMPT_ONE"}],
                "temperature": 0.5,
                "top_p": 0.9,
                "max_tokens": 1000,
            },
        )
        self.assertEqual(call_kwargs["timeout"], 60)
        self.assertNotIn("stream", call_kwargs["json"])
        self.assertNotIn("response_format", call_kwargs["json"])

        # With stop sequence
        mock_post.reset_mock()
        self.llm.invoke("PROMPT_TWO", stop=["END_JSON"])
        call_kwargs_stop = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs_stop["json"]["stop"], ["END_JSON"])

    # 3. LangChain PromptTemplate | CompanyLLM pipeline compatibility
    @patch("requests.post")
    def test_03_langchain_prompt_template_chain_invocation(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Chain output OK"}}]
        }
        mock_post.return_value = mock_response

        prompt = PromptTemplate(
            template="Analyze change: {title}",
            input_variables=["title"],
        )
        chain = prompt | self.llm
        output = chain.invoke({"title": "MFA Step-Up"})

        self.assertEqual(output, "Chain output OK")
        sent_prompt = mock_post.call_args.kwargs["json"]["messages"][0]["content"]
        self.assertEqual(sent_prompt, "Analyze change: MFA Step-Up")
        self.assertEqual(self.llm._llm_type, "company_llama")
        self.assertNotIn("api_key", self.llm._identifying_params)
        self.assertEqual(self.llm._identifying_params["model"], self.model_name)

    # 4. Missing credentials & unconfigured detection
    @patch("requests.post")
    def test_04_missing_credentials_and_placeholders(self, mock_post):
        unconfigured_cases = [
            CompanyLLM(model="", endpoint_url=self.endpoint_url, api_key=self.secret_key),
            CompanyLLM(model=self.model_name, endpoint_url="", api_key=self.secret_key),
            CompanyLLM(model=self.model_name, endpoint_url=self.endpoint_url, api_key=""),
            CompanyLLM(
                model="MODEL_IDENTIFIER",
                endpoint_url=self.endpoint_url,
                api_key=self.secret_key,
            ),
            CompanyLLM(
                model=self.model_name,
                endpoint_url=self.endpoint_url,
                api_key="PASTE_YOUR_API_KEY_HERE",
            ),
            CompanyLLM(
                model=self.model_name,
                endpoint_url="ftp://invalid.internal/llm",
                api_key=self.secret_key,
            ),
        ]
        for bad_llm in unconfigured_cases:
            self.assertFalse(bad_llm.is_configured())
            with self.assertRaises(CompanyLLMNotConfiguredError):
                bad_llm.invoke("Test prompt")

        mock_post.assert_not_called()

    # 5. HTTP 401 handling
    @patch("requests.post")
    def test_05_http_401_handling(self, mock_post):
        mock_401 = MagicMock(status_code=401)
        mock_401.raise_for_status.side_effect = requests.exceptions.HTTPError(
            f"401 Unauthorized for key {self.secret_key}",
            response=mock_401,
        )
        mock_post.return_value = mock_401

        with self.assertRaises(CompanyLLMError) as ctx:
            self.llm.invoke("Test prompt")

        self.assertIn("HTTP 401", str(ctx.exception))
        self.assertNotIn(self.secret_key, str(ctx.exception))

    # 6. HTTP 500 handling
    @patch("requests.post")
    def test_06_http_500_handling(self, mock_post):
        mock_500 = MagicMock(status_code=500)
        mock_500.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_500
        )
        mock_post.return_value = mock_500

        with self.assertRaises(CompanyLLMError) as ctx:
            self.llm.invoke("Test prompt")

        self.assertIn("HTTP 500", str(ctx.exception))
        self.assertNotIn(self.secret_key, str(ctx.exception))

    # 7. Timeout handling
    @patch("requests.post")
    def test_07_timeout_handling(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Timed out waiting for response")

        with self.assertRaises(CompanyLLMError) as ctx:
            self.llm.invoke("Test prompt")

        self.assertIn("timed out after 60 seconds", str(ctx.exception))
        self.assertNotIn(self.secret_key, str(ctx.exception))

    # 8. Network failure handling
    @patch("requests.post")
    def test_08_network_failure_handling(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError(
            f"Connection refused with key {self.secret_key}"
        )

        with self.assertRaises(CompanyLLMError) as ctx:
            self.llm.invoke("Test prompt")

        self.assertIn("Network connection", str(ctx.exception))
        self.assertNotIn(self.secret_key, str(ctx.exception))

    # 9. Invalid JSON response
    @patch("requests.post")
    def test_09_invalid_json_response(self, mock_post):
        mock_response = MagicMock(status_code=200)
        mock_response.json.side_effect = ValueError(f"Bad JSON containing {self.secret_key}")
        mock_post.return_value = mock_response

        with self.assertRaises(CompanyLLMResponseError) as ctx:
            self.llm.invoke("Test prompt")

        self.assertIn("valid JSON", str(ctx.exception))
        self.assertNotIn(self.secret_key, str(ctx.exception))

    # 10. Missing choices or message content
    @patch("requests.post")
    def test_10_missing_choices_or_message_content(self, mock_post):
        invalid_payloads = [
            ["not_a_dict"],
            {},
            {"choices": []},
            {"choices": "not_a_list"},
            {"choices": ["not_a_dict"]},
            {"choices": [{}]},
            {"choices": [{"message": "not_a_dict"}]},
            {"choices": [{"message": {}}]},
            {"choices": [{"message": {"content": None}}]},
            {"choices": [{"message": {"content": "   "}}]},
        ]
        for payload in invalid_payloads:
            mock_response = MagicMock(status_code=200)
            mock_response.json.return_value = payload
            mock_post.return_value = mock_response

            with self.assertRaises(CompanyLLMResponseError):
                self.llm.invoke("Test prompt")

    # 11. Lazy env loading, default values, and credential protection
    def test_11_lazy_config_defaults_and_secret_masking(self):
        # Class defaults must NOT read env vars at import time
        with patch.dict(
            os.environ,
            {
                "COMPANY_LLM_API_URL": self.endpoint_url,
                "COMPANY_LLM_API_KEY": self.secret_key,
                "COMPANY_LLM_MODEL_NAME": self.model_name,
            },
            clear=False,
        ):
            empty_instance = CompanyLLM()
            self.assertEqual(empty_instance.model, "")
            self.assertEqual(empty_instance.endpoint_url, "")
            self.assertEqual(empty_instance.api_key, "")
            self.assertFalse(empty_instance.is_configured())

            # Lazy settings & factory read env vars at call time
            settings = get_llm_settings()
            self.assertEqual(settings.company_llm_api_url, self.endpoint_url)
            self.assertEqual(settings.company_llm_model_name, self.model_name)
            self.assertEqual(settings.company_llm_temperature, 0.5)
            self.assertEqual(settings.company_llm_top_p, 0.9)
            self.assertEqual(settings.company_llm_max_tokens, 1000)
            self.assertEqual(settings.company_llm_timeout, 60)
            self.assertTrue(settings.is_configured())
            self.assertNotIn(self.secret_key, repr(settings))
            self.assertNotIn(self.secret_key, str(settings))

            lazy_llm = get_llm_model()
            self.assertTrue(lazy_llm.is_configured())
            self.assertNotIn(self.secret_key, repr(lazy_llm))
            self.assertNotIn(self.secret_key, str(lazy_llm))
            self.assertNotIn("api_key", lazy_llm.model_dump())
            self.assertIn("...", repr(lazy_llm))


if __name__ == "__main__":
    unittest.main()

