import os
from functools import lru_cache
from pydantic import BaseModel, Field


class RAGSettings(BaseModel):
    # Separately versioned collection name for future company embeddings
    collection_name: str = Field(
        default_factory=lambda: os.getenv(
            "RAG_COLLECTION_NAME", "testimpact_company_v1"
        )
    )
    chroma_dir: str = Field(
        default_factory=lambda: os.getenv("RAG_CHROMA_DIR", "./chroma_db")
    )
    # Company embedding API configuration placeholders
    company_embedding_api_url: str = Field(
        default_factory=lambda: os.getenv("COMPANY_EMBEDDING_API_URL", "")
    )
    company_embedding_api_key: str = Field(
        default_factory=lambda: os.getenv("COMPANY_EMBEDDING_API_KEY", "")
    )
    company_embedding_model: str = Field(
        default_factory=lambda: os.getenv("COMPANY_EMBEDDING_MODEL", "")
    )
    chunk_size: int = Field(
        default_factory=lambda: int(os.getenv("RAG_CHUNK_SIZE", "1000"))
    )
    chunk_overlap: int = Field(
        default_factory=lambda: int(os.getenv("RAG_CHUNK_OVERLAP", "100"))
    )


@lru_cache(maxsize=1)
def get_rag_settings() -> RAGSettings:
    """Returns cached RAG configuration settings."""
    return RAGSettings()
