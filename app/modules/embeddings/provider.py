from collections.abc import Sequence

import httpx

from app.core.config import EMBEDDING_VECTOR_DIMENSION, Settings
from app.core.exceptions import ExternalProviderException

EMBEDDING_PROVIDER_UNAVAILABLE = "Embedding provider is unavailable."
INVALID_EMBEDDING_RESPONSE = "Embedding provider returned invalid embeddings."


class OllamaEmbeddingProvider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        payload = {
            "model": self._settings.embedding_model,
            "input": list(texts),
            "truncate": False,
        }

        if self._client is not None:
            return await self._post_embeddings(self._client, payload, len(texts))

        async with httpx.AsyncClient(
            base_url=self._settings.ollama_base_url.rstrip("/"),
            timeout=self._settings.ollama_timeout_seconds,
        ) as client:
            return await self._post_embeddings(client, payload, len(texts))

    async def _post_embeddings(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, object],
        expected_count: int,
    ) -> list[list[float]]:
        try:
            response = await client.post("/api/embed", json=payload)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalProviderException(EMBEDDING_PROVIDER_UNAVAILABLE) from exc

        return _validated_embeddings(data, expected_count)


def _validated_embeddings(data: object, expected_count: int) -> list[list[float]]:
    if not isinstance(data, dict):
        raise ExternalProviderException(INVALID_EMBEDDING_RESPONSE)

    embeddings = data.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != expected_count:
        raise ExternalProviderException(INVALID_EMBEDDING_RESPONSE)

    return [_validated_vector(vector) for vector in embeddings]


def _validated_vector(vector: object) -> list[float]:
    if not isinstance(vector, list) or len(vector) != EMBEDDING_VECTOR_DIMENSION:
        raise ExternalProviderException(INVALID_EMBEDDING_RESPONSE)

    if any(isinstance(value, bool) or not isinstance(value, int | float) for value in vector):
        raise ExternalProviderException(INVALID_EMBEDDING_RESPONSE)

    return [float(value) for value in vector]
