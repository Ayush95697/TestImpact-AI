from app.routers.analysis import router as analysis_router
from app.routers.change_requests import router as change_requests_router
from app.routers.defects import router as defects_router
from app.routers.modules import router as modules_router
from app.routers.projects import router as projects_router
from app.routers.rag import router as rag_router
from app.routers.test_cases import router as test_cases_router
from app.routers.test_executions import router as test_executions_router

__all__ = [
    "projects_router",
    "modules_router",
    "test_cases_router",
    "defects_router",
    "test_executions_router",
    "change_requests_router",
    "rag_router",
    "analysis_router",
]
