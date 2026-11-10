from typing import List, Tuple
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.models.defect import Defect
from app.models.test_case import TestCase
from app.models.test_execution import TestExecution
from app.rag.config import get_rag_settings


def _get_text_splitter() -> RecursiveCharacterTextSplitter:
    settings = get_rag_settings()
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )


def build_test_case_documents(test_case: TestCase) -> List[Tuple[Document, str]]:
    """Converts a TestCase into one or more LangChain Documents with deterministic IDs."""
    module_names = (
        ", ".join(m.name for m in test_case.modules)
        if test_case.modules
        else "None"
    )

    content = (
        f"[Test Case]\n"
        f"Title: {test_case.title}\n"
        f"Priority: {test_case.priority}\n"
        f"Related Modules: {module_names}\n\n"
        f"Execution Steps:\n{test_case.steps}\n\n"
        f"Expected Result:\n{test_case.expected_result}"
    )

    base_metadata = {
        "project_id": test_case.project_id,
        "source_type": "test_case",
        "source_id": test_case.id,
        "test_case_id": test_case.id,
    }

    splitter = _get_text_splitter()
    chunks = splitter.split_text(content)

    results: List[Tuple[Document, str]] = []
    if len(chunks) <= 1:
        doc = Document(page_content=content, metadata=base_metadata)
        doc_id = f"test_case_{test_case.id}"
        results.append((doc, doc_id))
    else:
        for idx, chunk in enumerate(chunks):
            meta = dict(base_metadata)
            meta["chunk_index"] = idx
            doc = Document(page_content=chunk, metadata=meta)
            doc_id = f"test_case_{test_case.id}_chunk_{idx}"
            results.append((doc, doc_id))

    return results


def build_defect_documents(defect: Defect) -> List[Tuple[Document, str]]:
    """Converts a Defect into one or more LangChain Documents with deterministic IDs."""
    module_name = defect.module.name if defect.module else "Unknown"

    content = (
        f"[Defect Report]\n"
        f"Title: {defect.title}\n"
        f"Severity: {defect.severity}\n"
        f"Related Module: {module_name}\n\n"
        f"Description:\n{defect.description}\n\n"
        f"Resolution Notes:\n{defect.resolution_notes or 'Unresolved / None'}"
    )

    base_metadata = {
        "project_id": defect.project_id,
        "source_type": "defect",
        "source_id": defect.id,
    }

    splitter = _get_text_splitter()
    chunks = splitter.split_text(content)

    results: List[Tuple[Document, str]] = []
    if len(chunks) <= 1:
        doc = Document(page_content=content, metadata=base_metadata)
        doc_id = f"defect_{defect.id}"
        results.append((doc, doc_id))
    else:
        for idx, chunk in enumerate(chunks):
            meta = dict(base_metadata)
            meta["chunk_index"] = idx
            doc = Document(page_content=chunk, metadata=meta)
            doc_id = f"defect_{defect.id}_chunk_{idx}"
            results.append((doc, doc_id))

    return results


def build_test_execution_documents(
    execution: TestExecution,
) -> List[Tuple[Document, str]]:
    """Converts a TestExecution into one or more LangChain Documents with deterministic IDs."""
    test_case = execution.test_case
    tc_title = test_case.title if test_case else "Unknown"
    tc_steps = test_case.steps if test_case else "N/A"
    tc_expected = test_case.expected_result if test_case else "N/A"
    module_names = (
        ", ".join(m.name for m in test_case.modules)
        if test_case and test_case.modules
        else "None"
    )
    project_id = test_case.project_id if test_case else 0
    exec_date = (
        execution.executed_at.isoformat() if execution.executed_at else "Unknown"
    )

    content = (
        f"[Test Execution Record]\n"
        f"Execution Status: {execution.status}\n"
        f"Build Version: {execution.build_version or 'N/A'}\n"
        f"Execution Date: {exec_date}\n"
        f"Associated Test Case: {tc_title}\n"
        f"Priority: {test_case.priority if test_case else 'N/A'}\n"
        f"Related Modules: {module_names}\n\n"
        f"Test Steps:\n{tc_steps}\n\n"
        f"Expected Result:\n{tc_expected}"
    )

    base_metadata = {
        "project_id": project_id,
        "source_type": "test_execution",
        "source_id": execution.id,
        "test_case_id": execution.test_case_id,
    }

    splitter = _get_text_splitter()
    chunks = splitter.split_text(content)

    results: List[Tuple[Document, str]] = []
    if len(chunks) <= 1:
        doc = Document(page_content=content, metadata=base_metadata)
        doc_id = f"test_execution_{execution.id}"
        results.append((doc, doc_id))
    else:
        for idx, chunk in enumerate(chunks):
            meta = dict(base_metadata)
            meta["chunk_index"] = idx
            doc = Document(page_content=chunk, metadata=meta)
            doc_id = f"test_execution_{execution.id}_chunk_{idx}"
            results.append((doc, doc_id))

    return results

