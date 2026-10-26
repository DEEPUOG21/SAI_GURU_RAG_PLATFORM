import json

import httpx
import pytest

from app.services.llm import OpenCompatibleLLM


@pytest.mark.parametrize(
    "payload,valid",
    [
        ('data: {"choices":[{"delta":{"content":"Hello"}}]}\n\ndata: [DONE]\n\n', True),
        ('data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n', False),
        ("data: invalid-json\n\ndata: [DONE]\n\n", False),
    ],
)
async def test_llm_stream_protocol(monkeypatch, payload, valid):
    client_type = httpx.AsyncClient

    def factory(*args, **kwargs):
        return client_type(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, content=payload, headers={"Content-Type": "text/event-stream"}
                )
            )
        )

    monkeypatch.setattr("app.services.llm.httpx.AsyncClient", factory)
    if valid:
        assert (await OpenCompatibleLLM().complete([{"role": "user", "content": "q"}]))[0] == "Hello"
    else:
        with pytest.raises(ValueError):
            await OpenCompatibleLLM().complete([])


async def test_workflow_discards_unsupported_draft(monkeypatch):
    from app.agents import workflow
    from app.core.config import get_settings
    from app.retrieval.base import Candidate
    from app.security.scope import Scope
    from app.services.context import INSUFFICIENT

    class Retrieval:
        def __init__(self, db):
            pass

        async def retrieve(self, *args):
            return [Candidate("c", "d", "Leave.md", "24 days of leave.", None, "Annual leave", 1)]

    class Ranker:
        async def rerank(self, q, candidates):
            return candidates

    class LLM:
        async def stream(self, messages, *, json_mode=False):
            yield {"text": "Employees receive 99 days [Source 1]", "usage": {"total_tokens": 10}}

        async def complete(self, *args, **kwargs):
            return json.dumps({"supported": False, "reason": "Evidence says 24, not 99."}), None

    monkeypatch.setattr(workflow, "DenseRetriever", Retrieval)
    monkeypatch.setattr(workflow, "LexicalRetriever", Retrieval)
    monkeypatch.setattr(workflow, "reranker", lambda: Ranker())
    monkeypatch.setattr(workflow, "llm", lambda: LLM())
    monkeypatch.setattr(get_settings(), "generation_mode", "llm")
    monkeypatch.setattr(get_settings(), "grounding_action", "refuse")
    events = []

    async def emit(event, data):
        events.append((event, data))

    result = await workflow.execute(None, Scope("t", "u", "EMPLOYEE"), "What is our leave policy?", [], emit)
    assert result["answer"] == INSUFFICIENT
    assert result["citations"] == []
    assert not any(event == "draft" for event, _ in events), "Unverified tokens must stay private"
