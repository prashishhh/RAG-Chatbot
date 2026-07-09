from uuid import UUID, uuid4

from app.core.config import Settings
from app.core.exceptions import (
    ConflictException,
    ExternalProviderException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.core.responses import ApiResponse
from app.modules.auth.models import User
from app.modules.documents.models import Document, DocumentChunk, DocumentStatus
from app.modules.documents.repository import DocumentRepository
from app.modules.documents.schemas import (
    DeleteDocumentResponse,
    DocumentListItemResponse,
    DocumentResponse,
    EmbedDocumentResponse,
    IngestDocumentResponse,
)
from app.modules.embeddings.provider import OllamaEmbeddingProvider
from app.modules.ingestion.chunking import prepare_chunks
from app.modules.ingestion.extraction import extract_text
from app.modules.storage.security import (
    build_document_object_key,
    sanitize_filename,
    validate_file_extension,
    validate_file_size,
    validate_mime_type,
)
from app.modules.storage.service import LocalStorageService
from app.modules.workspaces.models import WorkspaceMember, WorkspaceRole
from app.modules.workspaces.repository import WorkspaceRepository

WORKSPACE_NOT_FOUND_MESSAGE = "Workspace not found."
DOCUMENT_NOT_FOUND_MESSAGE = "Document not found."
DOCUMENT_UPLOAD_DENIED_MESSAGE = "You do not have permission to upload documents."
DOCUMENT_DELETE_DENIED_MESSAGE = "You do not have permission to delete documents."
DOCUMENT_INGEST_DENIED_MESSAGE = "You do not have permission to ingest documents."
DOCUMENT_EMBED_DENIED_MESSAGE = "You do not have permission to embed documents."
DOCUMENT_UPLOAD_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MEMBER}
DOCUMENT_DELETE_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN}
DOCUMENT_INGEST_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MEMBER}
DOCUMENT_EMBED_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MEMBER}


class DocumentService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        workspace_repository: WorkspaceRepository,
        storage_service: LocalStorageService,
        settings: Settings,
        embedding_provider: OllamaEmbeddingProvider | None = None,
    ) -> None:
        self.document_repository = document_repository
        self.workspace_repository = workspace_repository
        self.storage_service = storage_service
        self.settings = settings
        self.embedding_provider = embedding_provider or OllamaEmbeddingProvider(settings)

    async def upload_async(
        self,
        workspace_id: UUID,
        filename: str,
        content_type: str | None,
        content: bytes,
        current_user: User,
    ) -> ApiResponse[DocumentResponse]:
        member = await self._get_active_workspace_member(workspace_id, current_user)
        if member.role not in DOCUMENT_UPLOAD_ROLES:
            raise ForbiddenException(DOCUMENT_UPLOAD_DENIED_MESSAGE)

        stored_filename = sanitize_filename(filename)
        validate_file_extension(stored_filename, self.settings.storage_allowed_extensions)
        normalized_content_type = validate_mime_type(
            content_type,
            self.settings.storage_allowed_mime_types,
        )
        validate_file_size(len(content), self.settings.storage_max_upload_bytes)

        document_id = uuid4()
        object_key = build_document_object_key(workspace_id, document_id, stored_filename)
        document = Document(
            id=document_id,
            workspace_id=workspace_id,
            uploaded_by_user_id=current_user.id,
            original_filename=stored_filename,
            stored_filename=stored_filename,
            object_key=object_key,
            content_type=normalized_content_type,
            size_bytes=len(content),
            status=DocumentStatus.UPLOADED,
        )

        self.storage_service.save_bytes(object_key, content)
        try:
            document = await self.document_repository.create_document(document)
        except Exception:
            self.storage_service.delete(object_key)
            raise

        return ApiResponse.success_response(
            message="Document uploaded successfully.",
            data=_document_response(document),
        )

    async def list_async(
        self,
        workspace_id: UUID,
        current_user: User,
    ) -> ApiResponse[list[DocumentListItemResponse]]:
        await self._get_active_workspace_member(workspace_id, current_user)
        documents = await self.document_repository.list_documents(workspace_id)

        return ApiResponse.success_response(
            message="Documents retrieved successfully.",
            data=[_document_list_item_response(document) for document in documents],
        )

    async def get_by_id_async(
        self,
        workspace_id: UUID,
        document_id: UUID,
        current_user: User,
    ) -> ApiResponse[DocumentResponse]:
        await self._get_active_workspace_member(workspace_id, current_user)
        document = await self.document_repository.get_document_by_id(workspace_id, document_id)
        if document is None:
            raise NotFoundException(DOCUMENT_NOT_FOUND_MESSAGE)

        return ApiResponse.success_response(
            message="Document retrieved successfully.",
            data=_document_response(document),
        )

    async def delete_async(
        self,
        workspace_id: UUID,
        document_id: UUID,
        current_user: User,
    ) -> ApiResponse[DeleteDocumentResponse]:
        member = await self._get_active_workspace_member(workspace_id, current_user)
        if member.role not in DOCUMENT_DELETE_ROLES:
            raise ForbiddenException(DOCUMENT_DELETE_DENIED_MESSAGE)

        document = await self.document_repository.get_document_by_id(workspace_id, document_id)
        if document is None:
            raise NotFoundException(DOCUMENT_NOT_FOUND_MESSAGE)

        document = await self.document_repository.soft_delete(document)

        return ApiResponse.success_response(
            message="Document deleted successfully.",
            data=DeleteDocumentResponse(
                documentId=document.id,
                status=document.status,
                deletedAt=document.deleted_at,
            ),
        )

    async def ingest_async(
        self,
        workspace_id: UUID,
        document_id: UUID,
        current_user: User,
    ) -> ApiResponse[IngestDocumentResponse]:
        member = await self._get_active_workspace_member(workspace_id, current_user)
        if member.role not in DOCUMENT_INGEST_ROLES:
            raise ForbiddenException(DOCUMENT_INGEST_DENIED_MESSAGE)

        document = await self.document_repository.get_document_by_id(workspace_id, document_id)
        if document is None:
            raise NotFoundException(DOCUMENT_NOT_FOUND_MESSAGE)
        if document.status == DocumentStatus.PROCESSING:
            raise ConflictException("Document ingestion is already processing.")

        await self.document_repository.mark_ingestion_processing(document)

        try:
            content = self.storage_service.read_bytes(document.object_key)
            extracted_items = extract_text(content, document.content_type)
            chunks = prepare_chunks(extracted_items)
            await self.document_repository.replace_chunks(document, chunks)
            document = await self.document_repository.mark_ingestion_ready(
                document,
                sum(chunk.char_count for chunk in chunks),
            )
        except ValidationException as exc:
            await self.document_repository.mark_ingestion_failed(document, exc.message)
            raise
        except Exception:
            await self.document_repository.mark_ingestion_failed(
                document,
                "Document ingestion failed.",
            )
            raise

        return ApiResponse.success_response(
            message="Document ingested successfully.",
            data=IngestDocumentResponse(
                documentId=document.id,
                status=document.status,
                chunkCount=len(chunks),
                textCharCount=document.text_char_count or 0,
                ingestionStartedAt=document.ingestion_started_at,
                ingestionCompletedAt=document.ingestion_completed_at,
            ),
        )

    async def embed_async(
        self,
        workspace_id: UUID,
        document_id: UUID,
        current_user: User,
    ) -> ApiResponse[EmbedDocumentResponse]:
        member = await self._get_active_workspace_member(workspace_id, current_user)
        if member.role not in DOCUMENT_EMBED_ROLES:
            raise ForbiddenException(DOCUMENT_EMBED_DENIED_MESSAGE)

        document = await self.document_repository.get_document_by_id(workspace_id, document_id)
        if document is None:
            raise NotFoundException(DOCUMENT_NOT_FOUND_MESSAGE)
        if document.status != DocumentStatus.READY:
            raise ConflictException("Document must be ingested before embedding.")

        chunks = await self.document_repository.list_chunks_needing_embeddings(
            workspace_id,
            document_id,
        )
        if not chunks:
            return ApiResponse.success_response(
                message="Document embeddings are already up to date.",
                data=EmbedDocumentResponse(
                    documentId=document.id,
                    status=document.status,
                    embeddedChunkCount=0,
                ),
            )

        await self.document_repository.mark_chunks_embedding_processing(chunks)

        try:
            embedded_count = await self._embed_chunks(chunks)
        except ExternalProviderException as exc:
            await self.document_repository.mark_chunks_embedding_failed(chunks, exc.message)
            raise
        except Exception:
            await self.document_repository.mark_chunks_embedding_failed(
                chunks,
                "Document embedding failed.",
            )
            raise

        return ApiResponse.success_response(
            message="Document embedded successfully.",
            data=EmbedDocumentResponse(
                documentId=document.id,
                status=document.status,
                embeddedChunkCount=embedded_count,
            ),
        )

    async def _embed_chunks(self, chunks: list[DocumentChunk]) -> int:
        embedded_count = 0
        batch_size = self.settings.embedding_batch_size
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            vectors = await self.embedding_provider.embed_texts([chunk.content for chunk in batch])
            if len(vectors) != len(batch):
                raise ExternalProviderException("Embedding provider returned invalid embeddings.")
            await self.document_repository.mark_chunks_embedding_ready(
                list(zip(batch, vectors, strict=True))
            )
            embedded_count += len(batch)
        return embedded_count

    async def _get_active_workspace_member(
        self,
        workspace_id: UUID,
        current_user: User,
    ) -> WorkspaceMember:
        _require_active_user(current_user)
        member = await self.workspace_repository.get_member(workspace_id, current_user.id)
        if member is None:
            raise NotFoundException(WORKSPACE_NOT_FOUND_MESSAGE)

        workspace = await self.workspace_repository.get_workspace_by_id(workspace_id)
        if workspace is None or not workspace.is_active:
            raise NotFoundException(WORKSPACE_NOT_FOUND_MESSAGE)

        return member


def _require_active_user(user: User) -> None:
    if not user.is_active:
        raise ForbiddenException("User account is inactive.")


def _document_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        documentId=document.id,
        workspaceId=document.workspace_id,
        originalFilename=document.original_filename,
        contentType=document.content_type,
        sizeBytes=document.size_bytes,
        status=document.status,
        createdAt=document.created_at,
        updatedAt=document.updated_at,
    )


def _document_list_item_response(document: Document) -> DocumentListItemResponse:
    return DocumentListItemResponse(
        documentId=document.id,
        originalFilename=document.original_filename,
        contentType=document.content_type,
        sizeBytes=document.size_bytes,
        status=document.status,
        createdAt=document.created_at,
    )
