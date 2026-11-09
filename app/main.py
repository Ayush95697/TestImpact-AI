from typing import Dict
from fastapi import FastAPI

app = FastAPI(
    title="TestImpact AI",
    description="AI-powered Regression Test Impact Analysis",
    version="0.1.0",
)


@app.get("/health", summary="Health Check")
def health_check() -> Dict[str, str]:
    return {
        "status": "healthy",
        "application": "TestImpact AI",
    }
