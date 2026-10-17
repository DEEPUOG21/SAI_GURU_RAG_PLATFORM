from types import SimpleNamespace

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.database.session import get_db
from app.main import app


async def test_database_unavailable_returns_safe_readiness_error():
    class Broken:
        async def scalar(self, *args, **kwargs):
            raise RuntimeError("private-database-detail")

    async def dependency():
        yield Broken()

    app.dependency_overrides[get_db] = dependency
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/ready")
        assert response.status_code == 503
        assert "private-database-detail" not in response.text
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectError("private-provider-detail"),
        httpx.ReadTimeout("private-timeout-detail"),
        ValueError("malformed provider payload"),
    ],
)
async def test_failed_chat_emits_safe_error_and_terminal_event(monkeypatch, failure):
    from app.security.scope import Scope
    from app.services import chat

    query = SimpleNamespace(status="RUNNING")

    class DB:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args):
            return query

        async def scalars(self, *args):
            return SimpleNamespace(all=lambda: [])

        async def commit(self):
            pass

    async def failed(*args):
        raise failure

    async def connected():
        return False

    monkeypatch.setattr(chat, "Session", DB)
    monkeypatch.setattr(chat, "execute", failed)
    frames = [
        frame
        async for frame in chat.chat_stream(
            "q", "c", "question", Scope("t", "u", "EMPLOYEE"), [], SimpleNamespace(is_disconnected=connected)
        )
    ]
    content = "".join(frames)
    assert "event: error" in content and "event: done" in content
    assert str(failure) not in content and query.status == "FAILED"


async def test_embedding_and_reranker_failure_degrade_explicitly(monkeypatch):
    from app.agents import workflow
    from app.core.config import get_settings
    from app.retrieval.base import Candidate
    from app.security.scope import Scope

    class Dense:
        def __init__(self, db):
            pass

        async def retrieve(self, *args):
            raise httpx.ConnectError("embedding unavailable")

    class Lexical:
        def __init__(self, db):
            pass

        async def retrieve(self, *args):
            return [Candidate("c", "d", "Policy.md", "A real test excerpt.", None, "Policy", 1)]

    class Ranker:
        async def rerank(self, *args):
            raise httpx.ReadTimeout("reranker timeout")

    async def rollback():
        pass

    async def emit(*args):
        pass

    monkeypatch.setattr(workflow, "DenseRetriever", Dense)
    monkeypatch.setattr(workflow, "LexicalRetriever", Lexical)
    monkeypatch.setattr(workflow, "reranker", lambda: Ranker())
    monkeypatch.setattr(get_settings(), "generation_mode", "extractive")
    result = await workflow.execute(
        SimpleNamespace(rollback=rollback), Scope("t", "u", "EMPLOYEE"), "What is our leave policy?", [], emit
    )
    assert result["candidates"][0].reranker_score is None
    assert {s["node"] for s in result["trace"] if s["status"] == "degraded"} == {
        "dense_fallback",
        "reranker_fallback",
    }
    assert "test excerpt" in result["answer"]
