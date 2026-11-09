from app.routers.modules import router as modules_router
from app.routers.projects import router as projects_router
from app.routers.test_cases import router as test_cases_router

__all__ = ["projects_router", "modules_router", "test_cases_router"]
