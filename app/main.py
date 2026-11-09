from typing import Dict
from fastapi import FastAPI

from app.database import Base, engine
# Import all models and associations so that metadata contains all tables
from app.models import Module, Project, TestCase, test_case_modules  # noqa: F401
from app.routers import modules_router, projects_router, test_cases_router

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


@app.get("/health", summary="Health Check")
def health_check() -> Dict[str, str]:
    return {
        "status": "healthy",
        "application": "TestImpact AI",
    }
