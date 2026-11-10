from functools import lru_cache
import math
import os
from typing import Any, Dict, List, Optional
from langchain_core.embeddings import Embeddings
import requests

from app.rag.config import get_rag_settings


class CompanyEmbeddingError(RuntimeError):
    """Base exception for company embedding API operations."""
    pass


class CompanyEmbeddingNotConfiguredError(CompanyEmbeddingError):
    """Raised when RAG operations are attempted before the company embedding API is configured."""

    def __init__(
        self,
        message: str = (
            "Company embedding API is not yet configured. "
            "Awaiting approved company embedding API credentials, endpoint URL, and dimensions. "
            "Refer to docs/COMPANY_EMBEDDING_API_REQUIREMENTS.md for setup requirements."
        ),
    ):
        super().__init__(message)


class CompanyEmbeddingResponseError(CompanyEmbeddingError):
    """Raised when the company embedding API response is invalid, malformed, or fails validation."""
    pass


class CompanyEmbeddings(Embeddings):
    """LangChain Embeddings implementation for the company's approved embedding API.

    Adheres strictly to the company HTTP contract using single-text requests:
    - Method: POST
    - Header: X-API-KEY: <api_key>
    - Body: {"texts": [single_text], "dimensions": <dimensions>}
    - Response: {"embeddings": [...], "usage": {...}}
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        dimensions: Optional[int] = None,
        timeout: int = 30,
    ):
        self.api_url = (api_url or "").strip()
        self.api_key = (api_key or "").strip()
        self.dimensions = dimensions
        self.timeout = timeout

    def is_configured(self) -> bool:
        """Checks if the minimal required configuration for the company provider is present."""
        placeholder_values = {"", "PASTE_YOUR_API_KEY_HERE", "YOUR_API_KEY_HERE"}
        return bool(
            self.api_url
            and self.api_key
            and self.api_key not in placeholder_values
            and not self.api_key.startswith("PASTE_")
            and self.dimensions is not None
            and self.dimensions > 0
        )

    def _embed_single_text(self, text: str) -> List[float]:
        """Embeds a single text using one dedicated HTTP request to the company API.

        Validates the response structure, dimension count, and numeric values.
        """
        if not self.is_configured():
            raise CompanyEmbeddingNotConfiguredError()

        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": self.api_key,
        }
        payload = {
            "texts": [text],
            "dimensions": self.dimensions,
        }

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise CompanyEmbeddingError(
                f"Embedding API request timed out after {self.timeout} seconds"
            ) from None
        except requests.exceptions.ConnectionError:
            raise CompanyEmbeddingError(
                "Network connection to embedding API failed"
            ) from None
        except requests.exceptions.HTTPError:
            status_code = response.status_code if response is not None else "unknown"
            raise CompanyEmbeddingError(
                f"Embedding API request failed with HTTP {status_code}"
            ) from None
        except requests.exceptions.RequestException:
            raise CompanyEmbeddingError(
                "Embedding API request failed"
            ) from None

        try:
            data = response.json()
        except Exception:
            raise CompanyEmbeddingResponseError(
                "Embedding API response could not be parsed as valid JSON"
            ) from None

        if not isinstance(data, dict):
            raise CompanyEmbeddingResponseError(
                "Embedding API response must be a JSON object"
            )

        if "embeddings" not in data:
            raise CompanyEmbeddingResponseError(
                "Embedding API response missing mandatory 'embeddings' field"
            )

        raw_embeddings = data["embeddings"]
        if not isinstance(raw_embeddings, list):
            raise CompanyEmbeddingResponseError(
                "'embeddings' field in API response must be a list"
            )

        # Accept either a flat vector or a nested list with exactly one vector
        vector: List[Any]
        if len(raw_embeddings) > 0 and isinstance(raw_embeddings[0], list):
            if len(raw_embeddings) != 1:
                raise CompanyEmbeddingResponseError(
                    f"Expected 1 vector for single-text request, got {len(raw_embeddings)}"
                )
            vector = raw_embeddings[0]
        else:
            vector = raw_embeddings

        if not isinstance(vector, list):
            raise CompanyEmbeddingResponseError(
                "Extracted vector is not a list"
            )

        if self.dimensions is not None and len(vector) != self.dimensions:
            raise CompanyEmbeddingResponseError(
                f"Vector has dimension {len(vector)}, expected configured dimension {self.dimensions}"
            )

        validated_vector: List[float] = []
        for val_idx, val in enumerate(vector):
            # Reject booleans (bool is a subclass of int in Python) and non-numeric types
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise CompanyEmbeddingResponseError(
                    f"Vector contains non-numeric value at position {val_idx}"
                )
            float_val = float(val)
            if math.isnan(float_val) or math.isinf(float_val):
                raise CompanyEmbeddingResponseError(
                    f"Vector contains non-finite value at position {val_idx}"
                )
            validated_vector.append(float_val)

        return validated_vector

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generates embedding vectors for a list of document texts.

        Conforms to the LangChain Embeddings contract by returning one dense
        vector per input text, making one HTTP request per text.
        Preserves input ordering and fails atomically if any single request fails.
        """
        if not self.is_configured():
            raise CompanyEmbeddingNotConfiguredError()

        if not texts:
            return []

        results: List[List[float]] = []
        for text in texts:
            vector = self._embed_single_text(text)
            results.append(vector)

        return results

    def embed_query(self, text: str) -> List[float]:
        """Generates an embedding vector for a single query string.

        Calls _embed_single_text directly to avoid unnecessary document wrapping.
        """
        if not self.is_configured():
            raise CompanyEmbeddingNotConfiguredError()

        return self._embed_single_text(text)

    def __repr__(self) -> str:
        masked_key = (
            f"{self.api_key[:3]}...{self.api_key[-2:]}"
            if len(self.api_key) > 5
            else ("***" if self.api_key else "<unset>")
        )
        return (
            f"CompanyEmbeddings(api_url='{self.api_url}', "
            f"api_key='{masked_key}', "
            f"dimensions={self.dimensions}, "
            f"timeout={self.timeout})"
        )


# Backward-compatibility alias
CompanyEmbeddingProvider = CompanyEmbeddings


@lru_cache(maxsize=1)
def get_embedding_model() -> CompanyEmbeddings:
    """Returns a cached lazy-loaded singleton of CompanyEmbeddings."""
    settings = get_rag_settings()
    return CompanyEmbeddings(
        api_url=settings.company_embedding_api_url,
        api_key=settings.company_embedding_api_key,
        dimensions=settings.company_embedding_dimensions,
        timeout=settings.company_embedding_timeout,
    )
