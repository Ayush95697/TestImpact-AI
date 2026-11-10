# TestImpact AI

> **AI-Powered Regression Test Impact Analysis & Test Recommendation Engine**

TestImpact AI is an intelligent regression test selection and impact analysis platform designed for QA teams and software engineers. When code modifications or change requests are proposed, TestImpact AI analyzes system changes across architectural module boundaries, historical defect trends, and semantic similarity to deterministically identify and rank the existing test cases most likely to be affected.

---

## Table of Contents

- [Overview & Key Features](#overview--key-features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Installation & Setup](#installation--setup)
- [Environment Configuration](#environment-configuration)
- [Synthetic Demo Dataset](#synthetic-demo-dataset)
- [Running the Application](#running-the-application)
- [API Reference & Core Workflows](#api-reference--core-workflows)
- [Recommendation Scoring Engine](#recommendation-scoring-engine)
- [Running Automated Tests](#running-automated-tests)
- [Security & Data Governance](#security--data-governance)

---

## Overview & Key Features

Modern enterprise software systems accumulate thousands of automated and manual regression tests. Executing the entire suite for every change request is slow, resource-intensive, and delays release velocity.

**TestImpact AI solves this by serving as a transparent decision-support system:**
- **Deterministic Multi-Signal Scoring**: Combines structural module associations (+40 pts), semantic vector search (+25 pts), historical defect clustering (+20 pts), and execution history (+15 pts) up to a maximum score of 100.
- **Strict Project Isolation**: Enforces relational and vector metadata filtering ensuring queries for one project never leak or return test cases from another.
- **Enterprise Embedding Integration**: Connects to the corporate Text Embeddings API using a robust single-text request adapter producing 736-dimensional dense vectors.
- **ChromaDB Vector Store**: Local, persistent vector storage with deterministic document IDs preventing duplicate embeddings.
- **Human-in-the-Loop Review**: QA engineers can review, accept, or reject recommendations (`pending`, `accepted`, `rejected`) while preserving immutable historical run audits.
- **Zero Third-Party Cloud Leaks**: No proprietary code or test assets are transmitted to external LLM providers.

---

## System Architecture

```mermaid
flowchart TD
    QA["QA Engineer / CI Pipeline"] -->|POST /change-requests/{id}/analyze| API["FastAPI Application"]
    
    subgraph Core ["Impact Analysis Pipeline"]
        API --> SVC["Impact Analysis Service"]
        SVC -->|Fetch CR & Modules| DB[("SQLAlchemy / SQLite DB")]
        SVC -->|Query: Title + Desc + Modules| RAG["ChromaDB Vector Store"]
        RAG -->|736-dim Embedding| EMB["Company Embedding API"]
        
        RAG -->|Top-K Context Chunks| ENG["Recommendation Engine"]
        DB -->|Relational Test Cases & Modules| ENG
        
        ENG -->|1. Direct Module Matches (+40)| SCORE["Deterministic Multi-Signal Scorer"]
        ENG -->|2. Semantic Search Matches (+25)| SCORE
        ENG -->|3. Related Module Defects (+20)| SCORE
        ENG -->|4. Historical Executions (+15)| SCORE
        
        SCORE -->|Multi-Tier Ranking| RANK["Ranked Recommendations"]
    end
    
    RANK -->|Persist AnalysisRun & Recommendations| DB
    RANK -->|Return AnalysisResponse| QA
    QA -->|PATCH /recommendations/{id}/review| API
```

---

## Tech Stack

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (0.115+) & [Uvicorn](https://www.uvicorn.org/) (ASGI server)
- **Database & ORM**: [SQLAlchemy](https://www.sqlalchemy.org/) 2.x with SQLite (local development)
- **Data Validation & Schemas**: [Pydantic](https://docs.pydantic.dev/) 2.x
- **Vector Database**: [ChromaDB](https://www.trychroma.com/) (persistent local directory)
- **Vector Pipeline Abstraction**: [LangChain Core](https://python.langchain.com/) & `langchain-chroma`
- **HTTP Client**: [Requests](https://requests.readthedocs.io/) with custom retry & timeout protection
- **Environment Management**: [python-dotenv](https://github.com/theskumar/python-dotenv)

---

## Project Structure

```
testimpact-ai/
├── app/
│   ├── main.py                     # FastAPI application setup & router registration
│   ├── database.py                 # SQLite engine, session maker, & Base class
│   ├── models/                     # SQLAlchemy 2.x ORM models
│   │   ├── associations.py         # M2M tables: test_case_modules, change_request_modules
│   │   ├── project.py              # Project entity
│   │   ├── module.py               # Architectural module entity
│   │   ├── test_case.py            # TestCase entity (M2M with Module)
│   │   ├── defect.py               # Historical defect records
│   │   ├── test_execution.py       # Test execution runs & status
│   │   ├── change_request.py       # Software change requests
│   │   ├── analysis_run.py         # Analysis run tracking (running, completed, failed)
│   │   └── recommendation.py       # Ranked recommendations & score breakdown
│   ├── schemas/                    # Pydantic 2.x validation models
│   │   ├── project.py
│   │   ├── module.py
│   │   ├── test_case.py
│   │   ├── defect.py
│   │   ├── test_execution.py
│   │   ├── change_request.py
│   │   ├── rag.py                  # Index & Search request/response schemas
│   │   ├── analysis.py             # Analysis run request & response schemas
│   │   └── recommendation.py       # Recommendation & review schemas
│   ├── routers/                    # FastAPI route controllers
│   │   ├── projects.py             # Project CRUD (/projects)
│   │   ├── modules.py              # Module CRUD (/projects/{id}/modules, /modules/{id})
│   │   ├── test_cases.py           # TestCase CRUD (/test-cases)
│   │   ├── defects.py              # Defect CRUD (/defects)
│   │   ├── test_executions.py      # Execution CRUD (/test-executions)
│   │   ├── change_requests.py      # Change Request CRUD (/change-requests)
│   │   ├── rag.py                  # Vector index & search endpoints (/rag)
│   │   └── analysis.py             # Impact analysis & review endpoints
│   ├── rag/                        # RAG & Vector pipeline
│   │   ├── config.py               # RAG configuration settings & collection versioning
│   │   ├── embeddings.py           # Custom CompanyEmbeddings (LangChain adapter)
│   │   ├── document_builder.py     # Deterministic chunking & document preparation
│   │   ├── vector_store.py         # Chroma vector store singleton
│   │   ├── indexing.py             # Project record indexing into Chroma
│   │   └── retrieval.py            # Semantic retrieval with project isolation
│   └── services/                   # Business logic & recommendation engine
│       ├── recommendation_engine.py# Deterministic multi-signal scoring & ranking
│       └── impact_analysis.py      # End-to-end analysis execution service
├── docs/                           # Architectural guides & requirements
│   ├── SYNTHETIC_DATA_GUIDE.md     # Data dictionary & cross-project isolation tests
│   └── COMPANY_EMBEDDING_API_REQUIREMENTS.md # API contract specification
├── scripts/                        # Utility & operational CLI scripts
│   ├── seed_demo_data.py           # Safe, idempotent demo dataset seeder
│   └── verify_env_config.py        # Environment verification tool
├── tests/                          # Automated test suites
│   ├── test_company_embeddings.py  # 12 unit tests for embedding HTTP adapter
│   └── test_impact_analysis.py     # 20 integration tests for analysis engine
├── .env.example                    # Template environment file
├── requirements.txt                # Production dependency declarations
└── README.md                       # Project documentation
```

---

## Installation & Setup

### Prerequisites
- **Python**: Version 3.11 or higher
- **Git**

### 1. Clone the Repository & Navigate
```powershell
git clone <repository-url>
cd "TestImpact AI\testimpact-ai"
```

### 2. Set Up Virtual Environment
```powershell
python -m venv .venv

# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# On Linux/macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## Environment Configuration

Create a local `.env` file in the `testimpact-ai` directory based on `.env.example`:

```powershell
Copy-Item .env.example .env
```

Populate `.env` with your settings:

```ini
# Database
DATABASE_URL=sqlite:///./testimpact.db

# Company Embedding API
COMPANY_EMBEDDING_API_URL=https://quasarmarket.coforge.com/qag/llmrouter-api/v2/text/embeddings
COMPANY_EMBEDDING_API_KEY=YOUR_ACTUAL_API_KEY_HERE
COMPANY_EMBEDDING_DIMENSIONS=736
COMPANY_EMBEDDING_TIMEOUT=30

# ChromaDB Persistent Storage
RAG_CHROMA_DIR=./chroma_db
RAG_COLLECTION_NAME=testimpact_company_v1
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=100
```

> **Security Guarantee:** `.env` is declared in `.gitignore`. The application automatically masks API keys in string representations, logs, and exception tracebacks.

---

## Synthetic Demo Dataset

TestImpact AI includes a built-in safe, idempotent seeder providing realistic test engineering data across two isolated domains:
1. **DEMO - Banking Platform**: Financial transfers, session management, WebAuthn MFA, wire limits, account statement masking.
2. **DEMO - E-Commerce Platform**: Catalog browsing, multi-currency cart, Apple Pay checkout, coupon rounding, payment webhooks.

### Dataset Record Counts
| Entity Type | Banking Platform | E-Commerce Platform | Total Across Database |
| :--- | :---: | :---: | :---: |
| **Projects** | 1 | 1 | **2** |
| **Modules** | 4 | 4 | **8** |
| **Test Cases** | 8 | 8 | **16** |
| **Defects** | 5 | 5 | **10** |
| **Test Executions** | 16 | 16 | **32** |
| **Change Requests** | 3 | 3 | **6** |

### Seeding Commands
```powershell
# 1. Preview changes without modifying database (Dry Run):
python scripts/seed_demo_data.py --allow-demo-data --dry-run

# 2. Apply seed data to the local SQLite database:
python scripts/seed_demo_data.py --allow-demo-data
```

*(The `--allow-demo-data` safety guard prevents accidental seeding in production environments).*

---

## Running the Application

Start the local Uvicorn development server:

```powershell
python -m uvicorn app.main:app --reload
```

Once running:
- **Interactive Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc API Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check Endpoint**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## API Reference & Core Workflows

### 1. Indexing Knowledge Base into ChromaDB
Before semantic similarity can contribute to recommendations, index the project's records into vector storage:

```http
POST /rag/index
Content-Type: application/json

{
  "project_id": 1
}
```

*Response (200 OK):*
```json
{
  "project_id": 1,
  "total_indexed": 29,
  "test_cases_indexed": 8,
  "defects_indexed": 5,
  "test_executions_indexed": 16,
  "status": "completed"
}
```

### 2. Triggering Regression Impact Analysis
Analyze an incoming change request against existing test cases:

```http
POST /change-requests/1/analyze
Content-Type: application/json

{
  "top_k": 10
}
```

*Response (200 OK):*
```json
{
  "analysis_run_id": 1,
  "change_request_id": 1,
  "project_id": 1,
  "status": "completed",
  "total_recommendations": 3,
  "recommendations": [
    {
      "id": 1,
      "test_case_id": 1,
      "test_case_title": "Verify valid user login",
      "rank": 1,
      "score": 100.0,
      "impact_level": "High",
      "reason": "The test case is directly associated with the Authentication module affected by this change. Retrieved directly by semantic search matching the change request (rank #1). Related historical defect ('Session token expires prematurely under load') was retrieved in the same module. Historical test execution history (Execution (passed) build v1.2.0-final) was retrieved.",
      "score_breakdown": {
        "direct_module_match": 40.0,
        "semantic_search_match": 25.0,
        "related_defect_match": 20.0,
        "related_execution_match": 15.0
      },
      "supporting_evidence": [
        {
          "source_type": "module",
          "source_id": 1,
          "title": "Affected Module: Authentication",
          "module_id": 1,
          "module_name": "Authentication"
        },
        {
          "source_type": "test_case",
          "source_id": 1,
          "title": "Verify valid user login",
          "retrieval_rank": 1,
          "distance": 0.0821
        }
      ],
      "review_status": "pending"
    }
  ]
}
```

### 3. Reviewing Recommendations (Human-in-the-Loop)
QA engineers record their review decision directly via API:

```http
PATCH /recommendations/1/review
Content-Type: application/json

{
  "review_status": "accepted"
}
```

---

## Recommendation Scoring Engine

Recommendations are scored deterministically using transparent, additive weights:

$$\text{Total Score} = W_{\text{module}} + W_{\text{semantic}} + W_{\text{defect}} + W_{\text{execution}} \le 100.0$$

| Weight Key | Value | Criteria |
| :--- | :---: | :--- |
| `direct_module_match` | **+40.0** | Test case is directly mapped to an affected module via `test_case_modules`. |
| `semantic_search_match` | **+25.0** | Test case document was directly retrieved by Chroma semantic search. |
| `related_defect_match` | **+20.0** | A historical defect retrieved by vector search belongs to the test case's module. |
| `related_execution_match` | **+15.0** | A historical execution record retrieved by vector search belongs to this test case. |

### Classification Levels
- **High** ($\ge 70.0$): Urgent regression target; multiple primary signals match.
- **Medium** ($40.0 \le \text{Score} < 70.0$): Secondary target; direct module or defect correlation.
- **Low** ($> 0.0$ and $< 40.0$): Tertiary target; indirect historical context.

---

## Running Automated Tests

The codebase includes full automated test coverage using mocked HTTP responses and an in-memory SQLite database, requiring no live external network calls.

### 1. Run Company Embedding Adapter Tests (12 tests)
Validates single-text request construction, 736-dim vector validation, atomic batch failures, and API key protection:
```powershell
python -m unittest tests/test_company_embeddings.py
```

### 2. Run Impact Analysis & Recommendation Engine Tests (20 tests)
Validates candidate generation, deduplication, cross-project isolation, scoring, run persistence, and review decisions:
```powershell
python -m unittest tests/test_impact_analysis.py
```

### 3. Run the Entire Test Suite
```powershell
python -m unittest discover tests
```

---

## Security & Data Governance

1. **Zero LLM Data Exfiltration**: TestImpact AI uses a local vector retrieval and deterministic heuristic engine. No test cases, code snippets, or defect descriptions are ever forwarded to public third-party LLMs (e.g. OpenAI, Anthropic).
2. **Credential Confidentiality**:
   - `COMPANY_EMBEDDING_API_KEY` is never printed to terminal, written to logs, or exposed in error messages.
   - Exception handlers suppress raw request tracebacks (`from None`), safeguarding headers from leaking into trace logs.
   - The provider `repr()` masks the key automatically (`abc...yz`).
3. **Repository Cleanliness**:
   - `.env` and `*.db` are strictly ignored by `.gitignore`.
   - Model cache directories are restricted to root `/models/` without colliding with `app/models/`.

---

## License

This project is proprietary and confidential. Developed for regression test impact analysis within enterprise QA engineering workflows.
