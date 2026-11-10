import math
import unittest
from unittest.mock import MagicMock, patch
import requests

from app.rag.embeddings import (
    CompanyEmbeddingError,
    CompanyEmbeddingNotConfiguredError,
    CompanyEmbeddingResponseError,
    CompanyEmbeddings,
)


class TestCompanyEmbeddings(unittest.TestCase):
    """Unit test suite for CompanyEmbeddings adapter with mocked HTTP calls."""

    def setUp(self):
        self.api_url = "https://quasarmarket.coforge.com/qag/llmrouter-api/v2/text/embeddings"
        self.secret_key = "super-secret-company-key-xyz123"
        self.dimensions = 736
        self.provider = CompanyEmbeddings(
            api_url=self.api_url,
            api_key=self.secret_key,
            dimensions=self.dimensions,
            timeout=15,
        )
        self.dummy_vector_736 = [0.001 * (i % 50) for i in range(736)]
        self.dummy_vector_736_b = [0.002 * (i % 50) for i in range(736)]

    # 1. Single-text embedding returns 736 dimensions
    @patch("requests.post")
    def test_01_single_text_returns_736_dimensions(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "embeddings": self.dummy_vector_736,
            "usage": {"input_tokens": 8, "duration": 0.3},
        }
        mock_post.return_value = mock_response

        query_vec = self.provider.embed_query("Sample search query")
        self.assertEqual(len(query_vec), 736)
        self.assertEqual(query_vec, self.dummy_vector_736)

    # 2. Two input texts generate two separate HTTP requests
    @patch("requests.post")
    def test_02_two_texts_generate_two_separate_requests(self, mock_post):
        resp_1 = MagicMock(status_code=200, json=lambda: {"embeddings": self.dummy_vector_736})
        resp_2 = MagicMock(status_code=200, json=lambda: {"embeddings": self.dummy_vector_736_b})
        mock_post.side_effect = [resp_1, resp_2]

        self.provider.embed_documents(["text 1", "text 2"])
        self.assertEqual(mock_post.call_count, 2)

    # 3. Each request contains exactly one text
    @patch("requests.post")
    def test_03_each_request_contains_exactly_one_text(self, mock_post):
        resp_1 = MagicMock(status_code=200, json=lambda: {"embeddings": self.dummy_vector_736})
        resp_2 = MagicMock(status_code=200, json=lambda: {"embeddings": self.dummy_vector_736_b})
        mock_post.side_effect = [resp_1, resp_2]

        self.provider.embed_documents(["document A", "document B"])
        first_call_json = mock_post.call_args_list[0].kwargs["json"]
        second_call_json = mock_post.call_args_list[1].kwargs["json"]

        self.assertEqual(first_call_json, {"texts": ["document A"], "dimensions": 736})
        self.assertEqual(second_call_json, {"texts": ["document B"], "dimensions": 736})

    # 4. Two input texts return exactly two vectors
    @patch("requests.post")
    def test_04_two_input_texts_return_two_vectors(self, mock_post):
        resp_1 = MagicMock(status_code=200, json=lambda: {"embeddings": self.dummy_vector_736})
        resp_2 = MagicMock(status_code=200, json=lambda: {"embeddings": self.dummy_vector_736_b})
        mock_post.side_effect = [resp_1, resp_2]

        vectors = self.provider.embed_documents(["text 1", "text 2"])
        self.assertEqual(len(vectors), 2)

    # 5. Output ordering matches input ordering
    @patch("requests.post")
    def test_05_output_ordering_matches_input_ordering(self, mock_post):
        resp_1 = MagicMock(status_code=200, json=lambda: {"embeddings": self.dummy_vector_736})
        resp_2 = MagicMock(status_code=200, json=lambda: {"embeddings": self.dummy_vector_736_b})
        mock_post.side_effect = [resp_1, resp_2]

        vectors = self.provider.embed_documents(["ordered first", "ordered second"])
        self.assertEqual(vectors[0], self.dummy_vector_736)
        self.assertEqual(vectors[1], self.dummy_vector_736_b)

    # 6. Every vector contains 736 dimensions
    @patch("requests.post")
    def test_06_every_vector_contains_736_dimensions(self, mock_post):
        resp_1 = MagicMock(status_code=200, json=lambda: {"embeddings": self.dummy_vector_736})
        resp_2 = MagicMock(status_code=200, json=lambda: {"embeddings": self.dummy_vector_736_b})
        mock_post.side_effect = [resp_1, resp_2]

        vectors = self.provider.embed_documents(["doc 1", "doc 2"])
        self.assertEqual(len(vectors[0]), 736)
        self.assertEqual(len(vectors[1]), 736)

    # 7. Empty document list returns an empty list without API calls
    @patch("requests.post")
    def test_07_empty_document_list_no_api_calls(self, mock_post):
        vectors = self.provider.embed_documents([])
        self.assertEqual(vectors, [])
        mock_post.assert_not_called()

    # 8. Invalid dimensions are rejected
    @patch("requests.post")
    def test_08_rejection_of_dimension_mismatch(self, mock_post):
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {
            "embeddings": [0.1] * 735  # 735 instead of configured 736
        }
        mock_post.return_value = mock_response

        with self.assertRaises(CompanyEmbeddingResponseError) as ctx:
            self.provider.embed_documents(["sample text"])

        self.assertIn("dimension 735, expected configured dimension 736", str(ctx.exception))

    # 9. HTTP 401 and 500 handling remains correct
    @patch("requests.post")
    def test_09_http_401_and_500_handling(self, mock_post):
        # 401 Unauthorized
        mock_401 = MagicMock(status_code=401)
        mock_401.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_401)
        mock_post.return_value = mock_401
        with self.assertRaises(CompanyEmbeddingError) as ctx_401:
            self.provider.embed_documents(["text"])
        self.assertIn("HTTP 401", str(ctx_401.exception))
        self.assertNotIn(self.secret_key, str(ctx_401.exception))

        # 500 Internal Server Error
        mock_500 = MagicMock(status_code=500)
        mock_500.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_500)
        mock_post.return_value = mock_500
        with self.assertRaises(CompanyEmbeddingError) as ctx_500:
            self.provider.embed_documents(["text"])
        self.assertIn("HTTP 500", str(ctx_500.exception))
        self.assertNotIn(self.secret_key, str(ctx_500.exception))

    # 10. Timeout handling remains correct
    @patch("requests.post")
    def test_10_timeout_handling(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out after 15s")

        with self.assertRaises(CompanyEmbeddingError) as ctx:
            self.provider.embed_documents(["text"])

        self.assertIn("timed out after 15 seconds", str(ctx.exception))
        self.assertNotIn(self.secret_key, str(ctx.exception))

    # 11. API key is never exposed
    @patch("requests.post")
    def test_11_api_key_confidentiality(self, mock_post):
        # String representation mask
        provider_repr = repr(self.provider)
        self.assertNotIn(self.secret_key, provider_repr)
        self.assertIn("...", provider_repr)

        # Network connection error mask
        mock_post.side_effect = requests.exceptions.ConnectionError(
            f"Failed to connect to {self.api_url} with key {self.secret_key}"
        )
        try:
            self.provider.embed_documents(["test"])
        except Exception as exc:
            self.assertNotIn(self.secret_key, str(exc))

        # JSON parsing error mask
        mock_response = MagicMock(status_code=200)
        mock_response.json.side_effect = ValueError(f"Corrupt JSON with {self.secret_key}")
        mock_post.side_effect = None
        mock_post.return_value = mock_response
        try:
            self.provider.embed_documents(["test"])
        except Exception as exc:
            self.assertNotIn(self.secret_key, str(exc))

    # 12. Failure of the second request does not return a partial successful result
    @patch("requests.post")
    def test_12_failure_of_second_request_fails_atomically(self, mock_post):
        resp_1 = MagicMock(status_code=200, json=lambda: {"embeddings": self.dummy_vector_736})
        # Second request encounters a timeout
        mock_post.side_effect = [
            resp_1,
            requests.exceptions.Timeout("Second request timed out"),
        ]

        texts = ["text 1 that succeeds", "text 2 that fails"]
        with self.assertRaises(CompanyEmbeddingError) as ctx:
            self.provider.embed_documents(texts)

        self.assertIn("timed out", str(ctx.exception))
        self.assertEqual(mock_post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
