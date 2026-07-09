from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.retrieval.schemas import (
    RETRIEVAL_SNIPPET_MAX_LENGTH,
    RETRIEVAL_TOP_K_DEFAULT,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalSearchResult,
)


def test_retrieval_search_request_defaults_and_trims_query() -> None:
    request = RetrievalSearchRequest(query="  What is the policy?  ")

    assert request.query == "What is the policy?"
    assert request.top_k == RETRIEVAL_TOP_K_DEFAULT


def test_retrieval_search_request_limits_top_k() -> None:
    with pytest.raises(ValidationError):
        RetrievalSearchRequest(query="question", topK=0)

    with pytest.raises(ValidationError):
        RetrievalSearchRequest(query="question", topK=21)


def test_retrieval_search_request_rejects_empty_query() -> None:
    with pytest.raises(ValidationError):
        RetrievalSearchRequest(query="   ")


def test_retrieval_result_is_citation_ready_and_safe() -> None:
    result = RetrievalSearchResult(
        documentId=uuid4(),
        documentName="Report.pdf",
        chunkId=uuid4(),
        pageNumber=3,
        snippet="Relevant excerpt",
        score=0.82,
    )

    payload = result.model_dump(by_alias=True)

    assert set(payload) == {
        "documentId",
        "documentName",
        "chunkId",
        "pageNumber",
        "snippet",
        "score",
    }
    assert "embedding" not in payload
    assert "vector" not in payload
    assert "objectKey" not in payload
    assert "content" not in payload


def test_retrieval_result_limits_snippet_and_score() -> None:
    with pytest.raises(ValidationError):
        RetrievalSearchResult(
            documentId=uuid4(),
            documentName="Report.pdf",
            chunkId=uuid4(),
            pageNumber=None,
            snippet="x" * (RETRIEVAL_SNIPPET_MAX_LENGTH + 1),
            score=0.5,
        )

    with pytest.raises(ValidationError):
        RetrievalSearchResult(
            documentId=uuid4(),
            documentName="Report.pdf",
            chunkId=uuid4(),
            pageNumber=None,
            snippet="Relevant excerpt",
            score=1.1,
        )


def test_retrieval_search_response_wraps_results() -> None:
    result = RetrievalSearchResult(
        documentId=uuid4(),
        documentName="Report.pdf",
        chunkId=uuid4(),
        pageNumber=None,
        snippet="Relevant excerpt",
        score=0.82,
    )

    response = RetrievalSearchResponse(results=[result])

    assert response.model_dump(by_alias=True)["results"][0]["documentName"] == "Report.pdf"
