from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.project import Project
from app.rag.embeddings import (
    CompanyEmbeddingError,
    CompanyEmbeddingNotConfiguredError,
    get_embedding_model,
)
from app.rag.indexing import index_project
from app.rag.retrieval import search_project_knowledge
from app.schemas.rag import IndexRequest, IndexResponse, SearchRequest, SearchResponse

router = APIRouter(
    prefix="/rag",
    tags=["RAG Knowledge Base"],
)


@router.post(
    "/index",
    response_model=IndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Index all project records into vector store",
)
def index_project_endpoint(
    request: IndexRequest,
    db: Session = Depends(get_db),
) -> IndexResponse:
    # 1. Check whether company embedding provider is configured
    embedding_provider = get_embedding_model()
    if not embedding_provider.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "RAG indexing is unavailable: Company embedding API is not yet configured. "
                "Awaiting approved company embedding API credentials, endpoint URL, and dimensions. "
                "Refer to docs/COMPANY_EMBEDDING_API_REQUIREMENTS.md for setup requirements."
            ),
        )

    # 2. Validate project existence
    project = db.query(Project).filter(Project.id == request.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {request.project_id} not found",
        )

    try:
        stats = index_project(project_id=request.project_id, db=db)
        return IndexResponse(**stats)
    except CompanyEmbeddingNotConfiguredError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except CompanyEmbeddingError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding provider error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to index project knowledge base: {str(e)}",
        )


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search project knowledge base with project isolation",
)
def search_knowledge_base_endpoint(
    request: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchResponse:
    # 1. Check whether company embedding provider is configured
    embedding_provider = get_embedding_model()
    if not embedding_provider.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "RAG search is unavailable: Company embedding API is not yet configured. "
                "Awaiting approved company embedding API credentials, endpoint URL, and dimensions. "
                "Refer to docs/COMPANY_EMBEDDING_API_REQUIREMENTS.md for setup requirements."
            ),
        )

    # 2. Validate project existence
    project = db.query(Project).filter(Project.id == request.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {request.project_id} not found",
        )

    try:
        raw_results = search_project_knowledge(
            project_id=request.project_id,
            query=request.query,
            top_k=request.top_k,
        )
        return SearchResponse(
            project_id=request.project_id,
            query=request.query,
            total_results=len(raw_results),
            results=raw_results,
        )
    except CompanyEmbeddingNotConfiguredError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except CompanyEmbeddingError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding provider error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search project knowledge base: {str(e)}",
        )
