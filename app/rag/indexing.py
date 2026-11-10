from typing import Any, Dict, List
from sqlalchemy.orm import Session

from app.models.defect import Defect
from app.models.test_case import TestCase
from app.models.test_execution import TestExecution
from app.rag.document_builder import (
    build_defect_documents,
    build_test_case_documents,
    build_test_execution_documents,
)
from app.rag.vector_store import get_vector_store


def index_project(project_id: int, db: Session) -> Dict[str, Any]:
    """Indexes all TestCases, Defects, and TestExecutions for a project into ChromaDB."""
    # 1. Fetch all records for the project
    test_cases = db.query(TestCase).filter(TestCase.project_id == project_id).all()
    defects = db.query(Defect).filter(Defect.project_id == project_id).all()
    test_executions = (
        db.query(TestExecution)
        .join(TestExecution.test_case)
        .filter(TestCase.project_id == project_id)
        .all()
    )

    # 2. Build documents with deterministic IDs
    all_docs = []
    all_ids = []

    tc_doc_count = 0
    for tc in test_cases:
        items = build_test_case_documents(tc)
        for doc, doc_id in items:
            all_docs.append(doc)
            all_ids.append(doc_id)
            tc_doc_count += 1

    defect_doc_count = 0
    for defect in defects:
        items = build_defect_documents(defect)
        for doc, doc_id in items:
            all_docs.append(doc)
            all_ids.append(doc_id)
            defect_doc_count += 1

    exec_doc_count = 0
    for execution in test_executions:
        items = build_test_execution_documents(execution)
        for doc, doc_id in items:
            all_docs.append(doc)
            all_ids.append(doc_id)
            exec_doc_count += 1

    vector_store = get_vector_store()

    # 3. Handle existing records in Chroma for this project to remove stale vectors
    try:
        existing_result = vector_store.get(where={"project_id": project_id})
        existing_ids = set(existing_result.get("ids", []))
    except Exception:
        existing_ids = set()

    current_ids = set(all_ids)
    stale_ids = list(existing_ids - current_ids)

    if stale_ids:
        vector_store.delete(ids=stale_ids)

    # 4. Add/Update current documents with deterministic IDs
    if all_docs:
        vector_store.add_documents(documents=all_docs, ids=all_ids)

    return {
        "project_id": project_id,
        "total_indexed": len(all_docs),
        "test_cases_indexed": tc_doc_count,
        "defects_indexed": defect_doc_count,
        "test_executions_indexed": exec_doc_count,
        "status": "completed",
    }

