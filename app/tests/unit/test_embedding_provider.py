import asyncio
import json

import httpx

from app.core.config import EMBEDDING_VECTOR_DIMENSION, LOCAL_JWT_SECRET_PLACEHOLDER, Settings
from app.core.exceptions import ExternalProviderException
from app.modules.embeddings.provider import (
    EMBEDDING_PROVIDER_UNAVAILABLE,
    INVALID_EMBEDDING_RESPONSE,
    OllamaEmbeddingProvider,
)


def make_settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost:5432/test",
        jwt_secret_key=LOCAL_JWT_SECRET_PLACEHOLDER,
        ollama_base_url="http://ollama.test",
    )


def make_client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url="http://ollama.test", transport=handler)


def test_ollama_provider_posts_batch_without_real_network() -> None:
    async def run_test() -> None:
        vector = [0.1] * EMBEDDING_VECTOR_DIMENSION
        seen_payload: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal seen_payload
            seen_payload = json.loads(request.content)
            return httpx.Response(200, json={"embeddings": [vector, vector]})

        async with make_client(httpx.MockTransport(handler)) as client:
            provider = OllamaEmbeddingProvider(make_settings(), client)

            result = await provider.embed_texts(["first chunk", "second chunk"])

        assert result == [vector, vector]
        assert seen_payload == {
            "model": "nomic-embed-text",
            "input": ["first chunk", "second chunk"],
            "truncate": False,
        }

    asyncio.run(run_test())


def test_ollama_provider_skips_empty_batch() -> None:
    async def run_test() -> None:
        called = False

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal called
            called = True
            return httpx.Response(500)

        async with make_client(httpx.MockTransport(handler)) as client:
            provider = OllamaEmbeddingProvider(make_settings(), client)

            result = await provider.embed_texts([])

        assert result == []
        assert called is False

    asyncio.run(run_test())


def test_ollama_provider_hides_provider_errors_and_input_text() -> None:
    async def run_test() -> None:
        document_text = "sensitive document content"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": document_text})

        async with make_client(httpx.MockTransport(handler)) as client:
            provider = OllamaEmbeddingProvider(make_settings(), client)

            try:
                await provider.embed_texts([document_text])
            except ExternalProviderException as exc:
                assert exc.message == EMBEDDING_PROVIDER_UNAVAILABLE
                assert document_text not in exc.message
            else:
                raise AssertionError("Expected ExternalProviderException")

    asyncio.run(run_test())


def test_ollama_provider_rejects_wrong_vector_dimension() -> None:
    async def run_test() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"embeddings": [[0.1, 0.2]]})

        async with make_client(httpx.MockTransport(handler)) as client:
            provider = OllamaEmbeddingProvider(make_settings(), client)

            try:
                await provider.embed_texts(["chunk"])
            except ExternalProviderException as exc:
                assert exc.message == INVALID_EMBEDDING_RESPONSE
            else:
                raise AssertionError("Expected ExternalProviderException")

    asyncio.run(run_test())


def test_ollama_provider_rejects_non_numeric_vectors() -> None:
    async def run_test() -> None:
        vector: list[object] = [0.1] * EMBEDDING_VECTOR_DIMENSION
        vector[0] = True

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"embeddings": [vector]})

        async with make_client(httpx.MockTransport(handler)) as client:
            provider = OllamaEmbeddingProvider(make_settings(), client)

            try:
                await provider.embed_texts(["chunk"])
            except ExternalProviderException as exc:
                assert exc.message == INVALID_EMBEDDING_RESPONSE
            else:
                raise AssertionError("Expected ExternalProviderException")

    asyncio.run(run_test())
