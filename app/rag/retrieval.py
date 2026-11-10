from typing import Any, Dict, List
from app.rag.vector_store import get_vector_store


def search_project_knowledge(
    project_id: int,
    query: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Searches the Chroma vector store for records matching query with strict project isolation."""
    vector_store = get_vector_store()

    # Search Chroma using project_id metadata filtering
    results_with_scores = vector_store.similarity_search_with_score(
        query=query,
        k=top_k,
        filter={"project_id": project_id},
    )

    formatted_results: List[Dict[str, Any]] = []
    for doc, distance in results_with_scores:
        meta = doc.metadata or {}
        formatted_results.append(
            {
                "page_content": doc.page_content,
                "source_type": meta.get("source_type", "unknown"),
                "source_id": meta.get("source_id", 0),
                "project_id": meta.get("project_id", project_id),
                "distance": round(float(distance), 4),
            }
        )

    return formatted_results

