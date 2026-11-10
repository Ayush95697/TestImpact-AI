import os
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables without overwriting pre-existing process environment
load_dotenv(override=False)


def _parse_optional_int(val: Optional[str]) -> Optional[int]:
    if not val:
        return None
    try:
        return int(val.strip())
    except (ValueError, TypeError):
        return None


class RAGSettings(BaseModel):
    # Separately versioned collection name for company embeddings
    collection_name: str = Field(
        default_factory=lambda: os.getenv(
            "RAG_COLLECTION_NAME", "testimpact_company_v1"
        )
    )
    chroma_dir: str = Field(
        default_factory=lambda: os.getenv("RAG_CHROMA_DIR", "./chroma_db")
    )
    # Company embedding API configuration
    company_embedding_api_url: str = Field(
        default_factory=lambda: os.getenv("COMPANY_EMBEDDING_API_URL", "").strip()
    )
    company_embedding_api_key: str = Field(
        default_factory=lambda: os.getenv("COMPANY_EMBEDDING_API_KEY", "").strip()
    )
    # Dimensions are strictly required by the company API contract and have no guessed default
    company_embedding_dimensions: Optional[int] = Field(
        default_factory=lambda: _parse_optional_int(
            os.getenv("COMPANY_EMBEDDING_DIMENSIONS")
        )
    )
    company_embedding_timeout: int = Field(
        default_factory=lambda: _parse_optional_int(
            os.getenv("COMPANY_EMBEDDING_TIMEOUT")
        )
        or 30
    )
    chunk_size: int = Field(
        default_factory=lambda: _parse_optional_int(os.getenv("RAG_CHUNK_SIZE"))
        or 1000
    )
    chunk_overlap: int = Field(
        default_factory=lambda: _parse_optional_int(os.getenv("RAG_CHUNK_OVERLAP"))
        or 100
    )


@lru_cache(maxsize=1)
def get_rag_settings() -> RAGSettings:
    """Returns cached RAG configuration settings."""
    return RAGSettings()
