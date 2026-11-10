from functools import lru_cache
from typing import List
from langchain_core.embeddings import Embeddings

from app.rag.config import get_rag_settings


class CompanyEmbeddingNotConfiguredError(RuntimeError):
    """Raised when RAG operations are attempted before the company embedding API is configured."""

    def __init__(
        self,
        message: str = (
            "Company embedding provider is not yet configured. "
            "Awaiting approved company embedding API documentation, endpoint URL, and credentials. "
            "Refer to docs/COMPANY_EMBEDDING_API_REQUIREMENTS.md for details."
        ),
    ):
        super().__init__(message)


class CompanyEmbeddingProvider(Embeddings):
    """LangChain Embeddings implementation boundary for the company's approved embedding API.

    This class adheres to LangChain's standard Embeddings interface without guessing
    the company's proprietary HTTP payload or authentication specification.
    """

    def __init__(self, api_url: str = "", api_key: str = "", model_name: str = ""):
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name

    def is_configured(self) -> bool:
        """Checks if the minimal configuration required for the company provider is present."""
        return bool(self.api_url and self.api_key)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a list of document strings using the company API."""
        if not self.is_configured():
            raise CompanyEmbeddingNotConfiguredError()
        raise NotImplementedError(
            "Company embedding API integration will be implemented once endpoint documentation is provided."
        )

    def embed_query(self, text: str) -> List[float]:
        """Generates an embedding for a query string using the company API."""
        if not self.is_configured():
            raise CompanyEmbeddingNotConfiguredError()
        raise NotImplementedError(
            "Company embedding API integration will be implemented once endpoint documentation is provided."
        )


@lru_cache(maxsize=1)
def get_embedding_model() -> CompanyEmbeddingProvider:
    """Returns a cached lazy-loaded instance of CompanyEmbeddingProvider."""
    settings = get_rag_settings()
    return CompanyEmbeddingProvider(
        api_url=settings.company_embedding_api_url,
        api_key=settings.company_embedding_api_key,
        model_name=settings.company_embedding_model,
    )
