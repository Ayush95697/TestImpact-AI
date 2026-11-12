import os
from typing import Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
# Import all models and associations so metadata registers all tables
from app.models import (  # noqa: F401
    AnalysisExplanation,
    AnalysisRun,
    ChangeRequest,
    Defect,
    Module,
    Project,
    Recommendation,
    TestCase,
    TestExecution,
    change_request_modules,
    test_case_modules,
)
from app.routers import (
    analysis_router,
    change_requests_router,
    defects_router,
    modules_router,
    projects_router,
    rag_router,
    system_router,
    test_cases_router,
    test_executions_router,
)

load_dotenv(override=False)

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def get_allowed_cors_origins() -> List[str]:
    raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ORIGINS)
    origins = [
        origin.strip().rstrip("/")
        for origin in raw_origins.split(",")
        if origin.strip() and origin.strip() != "*"
    ]
    return origins or [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


# Create database tables if they do not exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TestImpact AI",
    description="AI-powered Regression Test Impact Analysis",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Authorization"],
)

# Register routers
app.include_router(projects_router)
app.include_router(modules_router)
app.include_router(test_cases_router)
app.include_router(defects_router)
app.include_router(test_executions_router)
app.include_router(change_requests_router)
app.include_router(rag_router)
app.include_router(analysis_router)
app.include_router(system_router)


@app.get("/health", summary="Health Check")
def health_check() -> Dict[str, str]:
    return {
        "status": "healthy",
        "application": "TestImpact AI",
    }
