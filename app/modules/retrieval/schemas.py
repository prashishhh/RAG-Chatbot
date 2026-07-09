from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RETRIEVAL_QUERY_MAX_LENGTH = 2000
RETRIEVAL_TOP_K_DEFAULT = 5
RETRIEVAL_TOP_K_MAX = 20
RETRIEVAL_SNIPPET_MAX_LENGTH = 500


class RetrievalSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=RETRIEVAL_QUERY_MAX_LENGTH)
    top_k: int = Field(
        default=RETRIEVAL_TOP_K_DEFAULT,
        alias="topK",
        ge=1,
        le=RETRIEVAL_TOP_K_MAX,
    )

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)


class RetrievalSearchResult(BaseModel):
    document_id: UUID = Field(alias="documentId")
    document_name: str = Field(alias="documentName")
    chunk_id: UUID = Field(alias="chunkId")
    page_number: int | None = Field(alias="pageNumber")
    snippet: str = Field(max_length=RETRIEVAL_SNIPPET_MAX_LENGTH)
    score: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(populate_by_name=True)


class RetrievalSearchResponse(BaseModel):
    results: list[RetrievalSearchResult]

    model_config = ConfigDict(populate_by_name=True)
