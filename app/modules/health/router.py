from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.database import get_db
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_active_user
from app.modules.auth.models import User
from app.modules.health.schemas import DependencyHealthResponse, HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=ApiResponse[HealthResponse])
async def health_check() -> ApiResponse[HealthResponse]:
    return ApiResponse.success_response(
        message="Application is healthy.",
        data=HealthResponse(
            status="healthy",
            service="knowbase-api",
            version="0.1.0",
            timestamp=datetime.now(UTC),
        ),
    )


@router.get("/db", response_model=ApiResponse[DependencyHealthResponse])
async def database_health(
    _current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[DependencyHealthResponse]:
    return ApiResponse.success_response(
        message="Database connection is healthy.",
        data=await _dependency_health(db, "postgresql"),
    )


@router.get("/vector-store", response_model=ApiResponse[DependencyHealthResponse])
async def vector_store_health(
    _current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[DependencyHealthResponse]:
    return ApiResponse.success_response(
        message="Vector store is healthy.",
        data=await _dependency_health(db, "pgvector"),
    )


async def _dependency_health(
    db: AsyncSession,
    provider: str,
) -> DependencyHealthResponse:
    started_at = datetime.now(UTC)
    await db.execute(text("SELECT 1"))
    latency_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)

    return DependencyHealthResponse(
        status="healthy",
        provider=provider,
        latency_ms=latency_ms,
    )
