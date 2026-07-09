from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_active_user
from app.modules.auth.models import User
from app.modules.retrieval.dependencies import get_retrieval_service
from app.modules.retrieval.schemas import RetrievalSearchRequest, RetrievalSearchResponse
from app.modules.retrieval.service import RetrievalService

router = APIRouter(prefix="/workspaces/{workspace_id}/retrieval", tags=["Retrieval"])


@router.post("/search", response_model=ApiResponse[RetrievalSearchResponse])
async def search_retrieval(
    workspace_id: UUID,
    request: RetrievalSearchRequest,
    current_user: Annotated[User, Depends(require_active_user)],
    service: Annotated[RetrievalService, Depends(get_retrieval_service)],
) -> ApiResponse[RetrievalSearchResponse]:
    return await service.search_async(workspace_id, request, current_user)
