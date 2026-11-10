import os
import sys
from fastapi.testclient import TestClient

# Ensure testimpact-ai root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200, f"Health check failed: {response.text}"
    data = response.json()
    assert data.get("status") == "healthy" or data.get("status") == "ok", f"Unexpected health status: {data}"
    print("[PASS] GET /health ->", response.status_code, data)

def test_crud_endpoints():
    endpoints = [
        "/projects/",
        "/modules/",
        "/test-cases/",
        "/defects/",
        "/test-executions/",
        "/change-requests/",
    ]
    for ep in endpoints:
        response = client.get(ep)
        assert response.status_code in (200, 404), f"GET {ep} failed: {response.status_code} - {response.text}"
        print(f"[PASS] GET {ep} -> {response.status_code}")

def test_rag_503_endpoints():
    # POST /rag/index
    resp_index = client.post("/rag/index", json={"project_id": 9999})
    assert resp_index.status_code == 503, f"Expected 503 for /rag/index, got {resp_index.status_code}: {resp_index.text}"
    data_index = resp_index.json()
    assert "Company embedding API" in data_index.get("detail", ""), f"Unexpected detail: {data_index}"
    print("[PASS] POST /rag/index -> 503:", data_index["detail"])

    # POST /rag/search
    resp_search = client.post("/rag/search", json={"project_id": 9999, "query": "test query"})
    assert resp_search.status_code == 503, f"Expected 503 for /rag/search, got {resp_search.status_code}: {resp_search.text}"
    data_search = resp_search.json()
    assert "Company embedding API" in data_search.get("detail", ""), f"Unexpected detail: {data_search}"
    print("[PASS] POST /rag/search -> 503:", data_search["detail"])

def test_no_huggingface_imports():
    forbidden_terms = [
        "HuggingFaceEmbeddings",
        "sentence_transformers",
        "sentence-transformers",
        "langchain_huggingface",
    ]
    app_dir = os.path.join(PROJECT_ROOT, "app")
    found_violations = []
    for root, dirs, files in os.walk(app_dir):
        for f in files:
            if f.endswith(".py"):
                file_path = os.path.join(root, f)
                with open(file_path, "r", encoding="utf-8") as fh:
                    content = fh.read()
                    for term in forbidden_terms:
                        if term in content:
                            found_violations.append((file_path, term))

    assert not found_violations, f"Found forbidden imports/terms in app/: {found_violations}"
    print("[PASS] Codebase scan: Zero HuggingFace / sentence-transformers references in app/.")

if __name__ == "__main__":
    print("=" * 60)
    print("Running Milestone 5 Verification Suite")
    print("=" * 60)
    test_health()
    test_crud_endpoints()
    test_rag_503_endpoints()
    test_no_huggingface_imports()
    print("=" * 60)
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)
