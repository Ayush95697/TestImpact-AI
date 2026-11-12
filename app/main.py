from typing import Dict

from fastapi import FastAPI

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
    test_cases_router,
    test_executions_router,
)

# Create database tables if they do not exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TestImpact AI",
    description="AI-powered Regression Test Impact Analysis",
    version="0.1.0",
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


@app.get("/health", summary="Health Check")
def health_check() -> Dict[str, str]:
    return {
        "status": "healthy",
        "application": "TestImpact AI",
    }
