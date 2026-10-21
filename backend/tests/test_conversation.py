import json

import pytest

from app.services.conversation import bounded_history, resolve_question


def test_history_retains_answers_without_old_source_labels_and_bounds_bytes():
    history = [
        {"role": "system", "content": "untrusted"},
        {"role": "user", "content": "Who is the founder?"},
        {"role": "assistant", "content": "Ada Lovelace [Source 1]"},
    ]
    assert bounded_history(history) == [history[1], {"role": "assistant", "content": "Ada Lovelace "}]
    bounded = bounded_history([{"role": "user", "content": "界" * 5000}] * 20)
    assert sum(len(m["content"].encode()) for m in bounded) <= 6000


def test_fallback_keeps_topic_across_multiple_followups():
    from app.services.conversation import fallback_resolution

    history = [
        {"role": "user", "content": "Explain our annual leave policy"},
        {"role": "assistant", "content": "24 days."},
        {"role": "user", "content": "How does it accrue?"},
        {"role": "assistant", "content": "Two days a month."},
    ]
    result = fallback_resolution("What about contractors?", history)
    assert result["route"] == "DOCUMENT" and "annual leave" in result["question"]


async def test_resolver_uses_assistant_referent():
    class Provider:
        async def complete(self, messages, **kwargs):
            content = messages[-1]["content"]
            assert "Assistant: Mahatma Gandhi." in content
            assert "Latest question: When was he born?" in content
            return json.dumps({"question": "When was Mahatma Gandhi born?", "route": "DIRECT"}), None

    result = await resolve_question(
        Provider(),
        "When was he born?",
        [
            {"role": "user", "content": "Who is the father of the nation in India?"},
            {"role": "assistant", "content": "Mahatma Gandhi."},
        ],
    )
    assert result["question"] == "When was Mahatma Gandhi born?"


@pytest.mark.parametrize("response", ["{}", '{"question":null}', "invalid"])
async def test_resolver_rejects_malformed_output(response):
    class Provider:
        async def complete(self, *args, **kwargs):
            return response, None

    with pytest.raises((ValueError, TypeError)):
        await resolve_question(Provider(), "Why?", [])


async def test_resolver_cannot_downgrade_explicit_company_request():
    class Provider:
        async def complete(self, *args, **kwargs):
            return '{"question":"What is our leave policy?","route":"DIRECT"}', None

    assert (await resolve_question(Provider(), "What is our leave policy?", []))["route"] == "DOCUMENT"


@pytest.mark.parametrize(
    "question,rewritten,expected",
    [
        ("Who leads it?", "Who leads Project Atlas?", "DOCUMENT"),
        ("What must the author describe?", "What must the code change author describe?", "DOCUMENT"),
        ("What is Python?", "What is Python?", "DIRECT"),
    ],
)
async def test_followup_preserves_company_scope_but_allows_topic_change(question, rewritten, expected):
    class Provider:
        async def complete(self, *args, **kwargs):
            return json.dumps({"question": rewritten}), None

    result = await resolve_question(
        Provider(),
        question,
        [
            {"role": "user", "content": "When does our Project Atlas launch?"},
            {"role": "assistant", "content": "15 October 2026."},
        ],
    )
    assert result["route"] == expected


async def test_general_guidance_is_labeled_and_has_no_citations(monkeypatch):
    from app.agents import workflow
    from app.core.config import get_settings
    from app.security.scope import Scope

    class Retriever:
        def __init__(self, db):
            pass

        async def retrieve(self, *args):
            return []

    class Ranker:
        async def rerank(self, question, candidates):
            return []

    class Provider:
        async def stream(self, messages, **kwargs):
            assert "NEVER assert company-specific facts" in messages[0]["content"]
            yield {"text": "Ask the HR team to confirm the applicable policy."}

    monkeypatch.setattr(workflow, "DenseRetriever", Retriever)
    monkeypatch.setattr(workflow, "LexicalRetriever", Retriever)
    monkeypatch.setattr(workflow, "reranker", lambda: Ranker())
    monkeypatch.setattr(workflow, "llm", lambda: Provider())
    monkeypatch.setattr(get_settings(), "generation_mode", "llm")
    monkeypatch.setattr(get_settings(), "general_fallback_enabled", True)
    events = []

    async def emit(event, data):
        events.append((event, data))

    result = await workflow.execute(
        None, Scope("t", "u", "EMPLOYEE"), "What is our sabbatical policy?", [], emit
    )
    assert result["grounding"] == "GENERAL_KNOWLEDGE"
    assert "not source-verified" in result["answer"] and not result["citations"]
    assert any(event == "reset" for event, _ in events)
