import asyncio
from abc import ABC, abstractmethod
from functools import lru_cache

import httpx

from app.core.config import get_settings


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalEmbedding(EmbeddingProvider):
    def __init__(self):
        self.model = None

    def _embed(self, texts):
        if self.model is None:
            from fastembed import TextEmbedding

            self.model = TextEmbedding(model_name=get_settings().embedding_model, threads=2)
        return [vector.tolist() for vector in self.model.embed(texts)]

    async def embed(self, texts):
        return await asyncio.to_thread(self._embed, texts)


class RemoteEmbedding(EmbeddingProvider):
    async def embed(self, texts):
        cfg = get_settings()
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                cfg.embedding_url,
                json={"input": texts, "model": cfg.embedding_model},
                headers={"Authorization": f"Bearer {cfg.inference_api_key}"} if cfg.inference_api_key else {},
            )
            response.raise_for_status()
            rows = sorted(response.json()["data"], key=lambda row: row["index"])
            return [row["embedding"] for row in rows]


@lru_cache
def embeddings() -> EmbeddingProvider:
    cfg = get_settings()
    if cfg.embedding_dimensions != 384:
        raise ValueError("This schema uses 384 dimensions. Migrate vectors before changing dimensions.")
    if cfg.embedding_provider == "local":
        return LocalEmbedding()
    if cfg.embedding_provider == "http" and cfg.embedding_url:
        return RemoteEmbedding()
    raise ValueError("Configure a local or http embedding provider.")
