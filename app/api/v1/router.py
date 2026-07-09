from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.documents.router import router as documents_router
from app.modules.health.router import router as health_router
from app.modules.retrieval.router import router as retrieval_router
from app.modules.workspaces.router import router as workspaces_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(documents_router)
api_router.include_router(health_router)
api_router.include_router(retrieval_router)
api_router.include_router(workspaces_router)
