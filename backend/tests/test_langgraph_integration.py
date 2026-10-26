import asyncio
from contextlib import contextmanager

import pytest

from app.agents import workflow
from app.core.config import get_settings
from app.observability import langsmith as observability
from app.retrieval.base import Candidate
from app.security.scope import Scope


@pytest.mark.parametrize("route", ["DIRECT", "DOCUMENT", "SQL", "HYBRID"])
async def test_graph_routes_only_to_authorized_tools(monkeypatch, route):
    calls = []
    scope = Scope("tenant", "user", "MANAGER" if route in {"SQL", "HYBRID"} else "EMPLOYEE")
    cfg = get_settings()
    monkeypatch.setattr(cfg, "generation_mode", "extractive")
    monkeypatch.setattr(cfg, "langsmith_tracing", False)
    monkeypatch.setattr(workflow, "fallback_resolution", lambda q, h: {"question": q, "route": route})

    class Retriever:
        def __init__(self, db):
            pass

        async def retrieve(self, question, passed_scope):
            assert passed_scope is scope
            calls.append("retrieve")
            return [Candidate("c", "d", "Leave.md", "24 days of annual leave.", None, "Annual", 1)]

    class Ranker:
        async def rerank(self, question, candidates):
            return candidates

    async def sql(question, passed_scope):
        assert passed_scope is scope
        calls.append("sql")
        return {"columns": ["employee_count"], "rows": [{"employee_count": 8}]}

    async def emit(*args):
        pass

    monkeypatch.setattr(workflow, "DenseRetriever", Retriever)
    monkeypatch.setattr(workflow, "LexicalRetriever", Retriever)
    monkeypatch.setattr(workflow, "reranker", lambda: Ranker())
    monkeypatch.setattr(workflow, "run_sql", sql)
    result = await workflow.execute(None, scope, "Explain leave", [], emit)
    assert result["route"] == route
    assert ("sql" in calls) == (route in {"SQL", "HYBRID"})
    assert ("retrieve" in calls) == (route in {"DOCUMENT", "HYBRID"})
    if route == "HYBRID":
        assert {c.get("kind", "document") for c in result["citations"]} == {"document", "sql"}


async def test_clarification_ends_graph_without_generation(monkeypatch):
    monkeypatch.setattr(get_settings(), "langsmith_tracing", False)

    async def emit(*args):
        pass

    result = await workflow.execute(None, Scope("t", "u", "EMPLOYEE"), "What is our policy?", [], emit)
    assert result["grounding"] == "CLARIFICATION"
    assert result["citations"] == []


async def test_concurrent_graph_requests_do_not_share_answers(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "generation_mode", "llm")
    monkeypatch.setattr(cfg, "langsmith_tracing", False)
    monkeypatch.setattr(workflow, "fallback_resolution", lambda q, h: {"question": q, "route": "DIRECT"})

    class Provider:
        async def stream(self, messages, **kwargs):
            await asyncio.sleep(0)
            yield {"text": messages[-1]["content"]}

    async def emit(*args):
        pass

    monkeypatch.setattr(workflow, "llm", lambda: Provider())
    results = await asyncio.gather(
        *[
            workflow.execute(None, Scope(t, "u", "EMPLOYEE"), q, [], emit)
            for t, q in [("tenant-a", "alpha"), ("tenant-b", "beta")]
        ]
    )
    assert "alpha" in results[0]["answer"] and "beta" not in results[0]["answer"]
    assert "beta" in results[1]["answer"] and "alpha" not in results[1]["answer"]


@pytest.mark.parametrize(
    "enabled,key,expected", [(False, "", False), (True, "", False), (True, "test-key", True)]
)
def test_tracing_opt_in_and_redaction(monkeypatch, enabled, key, expected):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "langsmith_tracing", enabled)
    monkeypatch.setattr(cfg, "langsmith_api_key", key)
    seen = {}

    def client(api_key, endpoint, hide_inputs, hide_outputs):
        assert api_key == "test-key"
        assert hide_inputs and hide_outputs
        return "fake-client"

    @contextmanager
    def context(**kwargs):
        seen.update(kwargs)
        yield

    monkeypatch.setattr(observability, "tracing_client", client)
    monkeypatch.setattr(observability, "tracing_context", context)
    with observability.tracing_scope(cfg):
        pass
    assert seen["enabled"] is expected


def test_tracing_client_failure_does_not_run_application_twice(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "langsmith_tracing", True)
    monkeypatch.setattr(cfg, "langsmith_api_key", "test-key")

    def fail(*args):
        raise RuntimeError("unavailable")

    monkeypatch.setattr(observability, "tracing_client", fail)
    calls = []
    with observability.tracing_scope(cfg):
        calls.append("application")
    assert calls == ["application"]
