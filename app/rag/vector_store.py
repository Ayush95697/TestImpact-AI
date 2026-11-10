from functools import lru_cache
from langchain_chroma import Chroma

from app.rag.config import get_rag_settings
from app.rag.embeddings import get_embedding_model


@lru_cache(maxsize=1)
def get_vector_store() -> Chroma:
    """Returns a cached persistent Chroma vector store instance."""
    settings = get_rag_settings()
    embeddings = get_embedding_model()

    return Chroma(
        collection_name=settings.collection_name,
        embedding_function=embeddings,
        persist_directory=settings.chroma_dir,
    )

