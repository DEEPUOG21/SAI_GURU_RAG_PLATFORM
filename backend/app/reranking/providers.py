import asyncio
from abc import ABC, abstractmethod
from functools import lru_cache

import httpx

from app.core.config import get_settings
from app.retrieval.base import Candidate


class RerankerProvider(ABC):
    @abstractmethod
    async def rerank(self, query: str, candidates: list[Candidate], k: int = 6) -> list[Candidate]: ...


class LocalReranker(RerankerProvider):
    def __init__(self):
        self.model = None

    def _scores(self, query, documents):
        if self.model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            self.model = TextCrossEncoder(model_name=get_settings().reranker_model, threads=2)
        return list(self.model.rerank(query, documents))

    async def rerank(self, query, candidates, k=6):
        if not candidates:
            return []
        scores = await asyncio.to_thread(self._scores, query, [c.text for c in candidates])
        if len(scores) != len(candidates):
            raise ValueError("Invalid reranker score count.")
        for item, score in zip(candidates, scores, strict=True):
            item.reranker_score = float(score)
        return sorted(candidates, key=lambda item: item.reranker_score, reverse=True)[:k]


class RemoteReranker(RerankerProvider):
    async def rerank(self, query, candidates, k=6):
        if not candidates:
            return []
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                get_settings().reranker_url,
                json={"query": query, "documents": [c.text for c in candidates]},
                headers={"Authorization": f"Bearer {get_settings().inference_api_key}"}
                if get_settings().inference_api_key
                else {},
            )
            response.raise_for_status()
        scores = response.json()["scores"]
        if len(scores) != len(candidates):
            raise ValueError("Invalid reranker score count.")
        for item, score in zip(candidates, scores, strict=True):
            item.reranker_score = float(score)
        return sorted(candidates, key=lambda item: item.reranker_score, reverse=True)[:k]


@lru_cache
def reranker() -> RerankerProvider:
    if get_settings().reranker_provider == "local":
        return LocalReranker()
    if get_settings().reranker_provider == "http" and get_settings().reranker_url:
        return RemoteReranker()
    raise ValueError("Configure a local or http reranker provider.")
