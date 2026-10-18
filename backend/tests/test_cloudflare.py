import json

import httpx
import pytest

from app.core.config import get_settings
from app.reranking.providers import CloudflareReranker, reranker
from app.retrieval.base import Candidate
from app.services.providers import RemoteEmbedding


@pytest.fixture
def cloudflare(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "reranker_provider", "cloudflare")
    monkeypatch.setattr(cfg, "reranker_url", "https://api.cloudflare.com/test/rerank")
    monkeypatch.setattr(cfg, "embedding_url", "https://api.cloudflare.com/test/embeddings")
    monkeypatch.setattr(cfg, "embedding_model", "@cf/baai/bge-small-en-v1.5")
    monkeypatch.setattr(cfg, "inference_api_key", "test-only-token")
    reranker.cache_clear()
    yield cfg
    reranker.cache_clear()


def mock_api(monkeypatch, handler):
    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs)
    )


def candidates():
    return [Candidate(str(i), "doc", "policy.txt", f"Passage {i}", None, "Policy", 1) for i in range(2)]


async def test_cloudflare_reranker_preserves_score_identity(monkeypatch, cloudflare):
    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-only-token"
        assert json.loads(request.content) == {
            "query": "policy", "contexts": [{"text": "Passage 0"}, {"text": "Passage 1"}], "top_k": 2
        }
        return httpx.Response(200, json={
            "success": True, "result": {"response": [{"id": 1, "score": .9}, {"id": 0, "score": .1}]}
        })

    mock_api(monkeypatch, handler)
    rows = candidates()
    result = await reranker().rerank("policy", rows, k=1)
    assert result == [rows[1]]
    assert rows[0].reranker_score == .1
    assert rows[1].reranker_score == .9


@pytest.mark.parametrize("rows", [
    [], [{"id": 0, "score": .1}],
    [{"id": 0, "score": .1}, {"id": 0, "score": .9}],
    [{"id": -1, "score": .1}, {"id": 1, "score": .9}],
    [{"id": 0, "score": .1}, {"id": 2, "score": .9}],
    [{"id": False, "score": .1}, {"id": 1, "score": .9}],
    [{"id": 0, "score": ".1"}, {"id": 1, "score": .9}],
    [{"id": 0}, {"id": 1, "score": .9}],
])
async def test_invalid_ranking_does_not_mutate_candidates(monkeypatch, cloudflare, rows):
    mock_api(monkeypatch, lambda request: httpx.Response(
        200, json={"success": True, "result": {"response": rows}}
    ))
    items = candidates()
    with pytest.raises(ValueError):
        await CloudflareReranker().rerank("policy", items)
    assert all(item.reranker_score is None for item in items)


@pytest.mark.parametrize("status,payload,error", [
    (429, {"success": False}, httpx.HTTPStatusError),
    (200, {"success": False, "errors": [{"message": "private"}]}, ValueError),
    (200, {"success": True, "result": {}}, ValueError),
])
async def test_cloudflare_failure_is_not_a_score(monkeypatch, cloudflare, status, payload, error):
    mock_api(monkeypatch, lambda request: httpx.Response(status, json=payload))
    with pytest.raises(error):
        await CloudflareReranker().rerank("policy", candidates())


async def test_empty_candidates_do_not_call_provider(monkeypatch, cloudflare):
    def unexpected(request):
        pytest.fail("Empty retrieval must not consume provider quota")

    mock_api(monkeypatch, unexpected)
    assert await CloudflareReranker().rerank("policy", []) == []


async def test_cloudflare_openai_embeddings_contract(monkeypatch, cloudflare):
    def handler(request):
        assert json.loads(request.content) == {
            "input": ["first", "second"], "model": "@cf/baai/bge-small-en-v1.5"
        }
        assert request.headers["Authorization"] == "Bearer test-only-token"
        return httpx.Response(200, json={"data": [
            {"index": 1, "embedding": [.2] * 384}, {"index": 0, "embedding": [.1] * 384}
        ]})

    mock_api(monkeypatch, handler)
    assert await RemoteEmbedding().embed(["first", "second"]) == [[.1] * 384, [.2] * 384]


def test_cloudflare_requires_key(cloudflare, monkeypatch):
    monkeypatch.setattr(cloudflare, "inference_api_key", "")
    with pytest.raises(ValueError):
        reranker()
