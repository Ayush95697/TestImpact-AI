from typing import Dict
from fastapi import FastAPI

from app.database import Base, engine
from app.models.project import Project  # Ensure models are imported before create_all
from app.routers.projects import router as projects_router

# Create database tables if they do not exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TestImpact AI",
    description="AI-powered Regression Test Impact Analysis",
    version="0.1.0",
)

# Register routers
app.include_router(projects_router)


@app.get("/health", summary="Health Check")
def health_check() -> Dict[str, str]:
    return {
        "status": "healthy",
        "application": "TestImpact AI",
    }
