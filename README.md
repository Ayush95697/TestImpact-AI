# TestImpact AI

> **TestImpactAI - Intelligence Test Coverage and Impact Analysis**
> *Understand Change Impact. Prioritize Regression Testing.*

TestImpact AI is an enterprise-ready regression test impact analysis and decision-support platform designed for QA teams and software engineers. When code modifications or change requests are proposed, TestImpact AI analyzes system changes across architectural module boundaries, historical defect trends, execution history, and semantic vector retrieval to deterministically identify and rank existing regression test cases most likely to be affected — with optional, evidence-grounded explanations powered by your enterprise LLaMA 3.1 8B deployment.

---

## Table of Contents

- [Overview & Key Features](#overview--key-features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Installation & Setup](#installation--setup)
- [Environment Configuration](#environment-configuration)
- [Synthetic Demo Dataset](#synthetic-demo-dataset)
- [Running the Application (Backend + Frontend)](#running-the-application-backend--frontend)
- [API Reference & Core Workflows](#api-reference--core-workflows)
- [Recommendation Scoring Engine](#recommendation-scoring-engine)
- [Running Automated Tests](#running-automated-tests)
- [Security & Data Governance](#security--data-governance)
- [Project Team](#project-team)

---

## Overview & Key Features

Modern enterprise software systems accumulate thousands of manual and automated regression tests. Executing every test after every change slows releases, while testing only a single modified component risks missing cross-module regressions.

**TestImpact AI serves as a transparent decision-support system:**
- **Deterministic Multi-Signal Scoring**: Combines direct module associations (`+40` pts), Chroma semantic search (`+25` pts), historical defect clustering (`+20` pts), and execution history (`+15` pts) up to a maximum heuristic score of `100`.
- **Strict Project Isolation**: Enforces relational and ChromaDB metadata filtering so queries for one project never leak or return test cases from another.
- **Enterprise Text Embeddings Integration**: Connects to the company Text Embeddings API via a single-text LangChain adapter producing 736-dimensional dense vectors.
- **Optional Grounded AI Explanations (LLaMA 3.1 8B)**: Generates non-blocking, evidence-cited executive and per-test explanations strictly after deterministic ranking. The LLM never creates test IDs, alters scores/ranks, or invents defects/evidence, and deterministic impact analysis remains fully operational even when the LLM is unconfigured or unavailable.
- **Human-in-the-Loop QA Review**: QA engineers inspect evidence, review recommendations (`pending`, `accepted`, `rejected`), and audit past analysis runs without altering historical scores or ranks.
- **Enterprise SaaS Web Application**: Responsive React + TypeScript + Tailwind CSS dashboard featuring Dark/Light themes, interactive project/asset CRUD workspaces, dynamic change request creation, impact results drill-down, run history filters, and documentation views.

---

## System Architecture

```mermaid
flowchart TD
    UI["React + TypeScript Frontend (Vite)"] -->|REST + CORS| API["FastAPI Backend"]

    subgraph Core ["Deterministic Impact Analysis Pipeline"]
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
    API -->|Optional POST /analysis-runs/{id}/explain| LLM["Company LLaMA 3.1 8B API (Advisory Only)"]
    LLM -->|Validated Evidence-Cited Notes| DB
    UI -->|PATCH /recommendations/{id}/review| API
```

---

## Tech Stack

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) & [Uvicorn](https://www.uvicorn.org/) (ASGI)
- **Database & ORM**: [SQLAlchemy](https://www.sqlalchemy.org/) 2.x with SQLite (`testimpact.db`)
- **Validation**: [Pydantic](https://docs.pydantic.dev/) 2.x
- **Vector Store & RAG**: [ChromaDB](https://www.trychroma.com/), `langchain-core`, `langchain-chroma`
- **Enterprise AI Integrations**: Company Text Embeddings API (`CompanyEmbeddings`) and optional Company LLaMA 3.1 8B (`CompanyLLM`) via `requests`
- **Configuration**: `python-dotenv`

### Frontend (`frontend/`)
- **Core**: [React](https://react.dev/) 18, [TypeScript](https://www.typescriptlang.org/), [Vite](https://vite.dev/)
- **Styling & Icons**: [Tailwind CSS](https://tailwindcss.com/) (Light/Dark theme tokens), `lucide-react`, `@fontsource/{inter,manrope,jetbrains-mono}`
- **Routing & State**: `react-router-dom` v6, `@tanstack/react-query`
- **Forms, Validation & Charts**: `react-hook-form`, `zod`, `@hookform/resolvers`, `recharts`, `axios`

---

## Project Structure

```text
testimpact-ai/
├── app/
│   ├── main.py                         # FastAPI app, CORS middleware & router registration
│   ├── database.py                     # SQLite engine, session maker & Base
│   ├── models/                         # SQLAlchemy 2.x ORM entities
│   │   ├── associations.py             # M2M tables: test_case_modules, change_request_modules
│   │   ├── project.py
│   │   ├── module.py
│   │   ├── test_case.py
│   │   ├── defect.py
│   │   ├── test_execution.py
│   │   ├── change_request.py
│   │   ├── analysis_run.py
│   │   ├── recommendation.py
│   │   └── analysis_explanation.py     # Persisted optional LLaMA 3.1 8B explanations
│   ├── schemas/                        # Pydantic v2 request/response contracts
│   │   ├── analysis.py
│   │   ├── change_request.py
│   │   ├── defect.py
│   │   ├── llm.py
│   │   ├── module.py
│   │   ├── project.py
│   │   ├── rag.py
│   │   ├── recommendation.py
│   │   ├── system.py                   # Capabilities & dashboard summary schemas
│   │   ├── test_case.py
│   │   └── test_execution.py
│   ├── routers/                        # REST controllers
│   │   ├── projects.py
│   │   ├── modules.py
│   │   ├── test_cases.py
│   │   ├── defects.py
│   │   ├── test_executions.py
│   │   ├── change_requests.py
│   │   ├── rag.py
│   │   ├── analysis.py                 # Analyze, list runs, review, optional explain
│   │   └── system.py                   # /system/capabilities & /dashboard/summary
│   ├── rag/                            # Embedding adapter, chunking, Chroma indexing & retrieval
│   │   ├── config.py
│   │   ├── embeddings.py
│   │   ├── document_builder.py
│   │   ├── vector_store.py
│   │   ├── indexing.py
│   │   └── retrieval.py
│   ├── llm/                            # Optional LLaMA 3.1 8B integration (advisory only)
│   │   ├── config.py
│   │   ├── provider.py
│   │   ├── prompts.py
│   │   └── explanation_service.py      # Strict grounding validation & DB persistence
│   └── services/                       # Deterministic multi-signal impact engine
│       ├── recommendation_engine.py
│       └── impact_analysis.py
├── frontend/                           # Standalone React + Vite + TypeScript frontend
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── index.css
│       ├── types/api.ts
│       ├── utils/formatters.ts
│       ├── contexts/                   # ThemeContext & ToastContext
│       ├── hooks/useSystemStatus.ts    # /health & /system/capabilities polling
│       ├── layouts/MainLayout.tsx      # Responsive sidebar + header shell
│       ├── services/                   # Modular Axios API clients
│       ├── components/                 # Common UI, charts, project modals, AI panels
│       └── pages/                      # Dashboard, Projects, CRs, Impact Analysis, History, About
├── docs/
├── scripts/                            # Demo seeder & environment verification scripts
├── tests/                              # Automated backend unit & integration test suites
├── .env.example
├── requirements.txt
├── run_server.bat                      # Windows launcher (starts Backend + Frontend together)
└── README.md
```

---

## Installation & Setup

### Prerequisites
- **Python**: Version 3.11 or higher
- **Node.js & npm**: Node.js 18+ (for the React frontend)
- **Git**

### 1. Navigate to the Project Root
```powershell
cd "TestImpact AI\testimpact-ai"
```

### 2. Backend Setup (Python Virtual Environment)
```powershell
python -m venv .venv

# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# Linux/macOS:
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Frontend Setup (`frontend/`)
```powershell
cd frontend
npm install
cd ..
```

---

## Environment Configuration

### 1. Backend Environment (`.env`)
Copy `.env.example` to `.env` inside `testimpact-ai/`:
```powershell
Copy-Item .env.example .env
```

Key backend variables:
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

# Optional Company LLM API (LLaMA 3.1 8B)
COMPANY_LLM_API_URL=
COMPANY_LLM_API_KEY=
COMPANY_LLM_MODEL_NAME=
COMPANY_LLM_TEMPERATURE=0.5
COMPANY_LLM_TOP_P=0.9
COMPANY_LLM_MAX_TOKENS=1000
COMPANY_LLM_TIMEOUT=60

# Frontend CORS Allowed Origins (comma-separated)
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

> **Security Note**: `.env` is ignored by Git. All embedding and LLM API keys remain strictly on the backend and are never exposed via `/system/capabilities`, error responses, or frontend configuration.

### 2. Frontend Environment (`frontend/.env`)
Copy `frontend/.env.example` to `frontend/.env`:
```powershell
Copy-Item frontend\.env.example frontend\.env
```

`frontend/.env` only stores the public backend URL:
```ini
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Never place any API keys, tokens, or secrets in `frontend/.env` or `VITE_*` variables.

---

## Synthetic Demo Dataset

TestImpact AI includes a safe, idempotent seeder across two isolated domains (`DEMO - Banking Platform` and `DEMO - E-Commerce Platform`):

```powershell
# Preview changes without modifying the database:
python scripts/seed_demo_data.py --allow-demo-data --dry-run

# Apply synthetic demo data:
python scripts/seed_demo_data.py --allow-demo-data
```

---

## Running the Application (Backend + Frontend)

### Windows Quick Launcher (`run_server.bat`)
Double-click `run_server.bat` or run it from PowerShell to validate dependencies and launch both the FastAPI Backend (`8000`) and React/Vite Frontend (`5173`) together:
```powershell
.\run_server.bat
```

### Manual Startup (Two Separate Terminals)

#### Terminal 1 — Start FastAPI Backend (`http://127.0.0.1:8000`)
```powershell
# From testimpact-ai/ (with .venv activated)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

#### Terminal 2 — Start React Frontend (`http://127.0.0.1:5173`)
```powershell
cd frontend
npm run dev
```

### Build Frontend for Production
```powershell
cd frontend
npm run build
```
*(Runs `tsc --noEmit && vite build` and outputs static assets to `frontend/dist/`.)*

### Application URLs
- **Web Application**: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- **Interactive Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## API Reference & Core Workflows

### System & Dashboard
- `GET /health`: Service health check
- `GET /system/capabilities`: Reports `{ "rag_available": bool, "llm_explanations_available": bool }` without exposing secrets
- `GET /dashboard/summary`: Read-only aggregate metrics, project overview counts, impact & execution distributions, and top 5 recent runs

### Core CRUD & Vector Indexing
- `/projects`, `/projects/{id}/modules`, `/modules/{id}`, `/test-cases`, `/defects`, `/test-executions`, `/change-requests`
- `POST /rag/index` (`{ "project_id": 1 }`) & `POST /rag/search`

### Impact Analysis, Review & Optional AI Explanations
1. **Trigger Analysis**: `POST /change-requests/{id}/analyze` with `{ "top_k": 10 }`
2. **Browse Persisted Runs**: `GET /analysis-runs?project_id=&status=&date_from=&date_to=&limit=20&offset=0`
3. **Inspect Run Detail**: `GET /analysis-runs/{analysis_run_id}`
4. **QA Review Decision**: `PATCH /recommendations/{recommendation_id}/review` with `{ "review_status": "accepted" | "rejected" }`
5. **Generate / Fetch Grounded LLM Explanation (Optional)**:
   - `POST /analysis-runs/{analysis_run_id}/explain`
   - `GET /analysis-runs/{analysis_run_id}/explanation`

---

## Recommendation Scoring Engine

Recommendations are scored deterministically using transparent additive heuristic weights (0–100 points — not probability percentages):

$$\text{Total Score} = W_{\text{module}} + W_{\text{semantic}} + W_{\text{defect}} + W_{\text{execution}} \le 100.0$$

| Weight Key | Points | Criteria |
| :--- | :---: | :--- |
| `direct_module_match` | **+40.0** | Test case is directly mapped to an affected module via `test_case_modules`. |
| `semantic_search_match` | **+25.0** | Test case document was directly retrieved by Chroma semantic search. |
| `related_defect_match` | **+20.0** | A historical defect retrieved by vector search belongs to the test case's module. |
| `related_execution_match` | **+15.0** | A historical execution record retrieved by vector search belongs to this test case. |

### Classification Levels
- **High** ($\ge 70.0$): Primary regression target; multiple deterministic & semantic signals match.
- **Medium** ($40.0 \le \text{Score} < 70.0$): Secondary target; direct module or defect correlation.
- **Low** ($> 0.0$ and $< 40.0$): Tertiary target; indirect historical context.

---

## Running Automated Tests

All backend automated tests use mocked HTTP transports and an isolated in-memory SQLite database:

```powershell
# Run the complete backend suite (56 tests across Milestones 5–9)
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Included suites:
- `tests/test_company_embeddings.py` (12 tests) — Embedding API adapter & 736-dim validation
- `tests/test_company_llm.py` (11 tests) — LLaMA 3.1 8B LangChain provider & secret masking
- `tests/test_impact_analysis.py` (20 tests) — Scoring, ranking, project isolation & QA review
- `tests/test_llm_explanations.py` (9 tests) — Strict LLM grounding & score/rank preservation
- `tests/test_milestone9_backend.py` (4 tests) — Capabilities, dashboard summary, run filtering & CORS

Frontend type-checking and build validation:
```powershell
cd frontend
npm run build
```

---

## Security & Data Governance

1. **Enterprise API Isolation**: Test artifacts are processed locally with SQLite + ChromaDB, calling only configured corporate embedding/LLM router endpoints.
2. **Credential Confidentiality**: Backend API keys are masked in `repr()`, excluded from error tracebacks (`from None`), omitted from `/system/capabilities`, and never stored in `frontend/`.
3. **CORS Restriction**: Backend `CORSMiddleware` only trusts explicitly listed `CORS_ALLOWED_ORIGINS` origins (defaulting to local Vite dev server origins without wildcard `*`).
4. **Repository Hygiene**: `.env`, `frontend/.env`, `frontend/node_modules/`, `frontend/dist/`, `*.db`, and `chroma_db/` are declared in `.gitignore`.

---

## Project Team

**Official Project Name:** TestImpactAI - Intelligence Test Coverage and Impact Analysis
**Team Name:** SynapseX
**Team Members:**
- Aastha Teotia
- Mankaran Saini
- Ayush Mishra
