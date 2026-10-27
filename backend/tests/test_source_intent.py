import json
from types import SimpleNamespace

import httpx
import pytest

from app.agents import workflow
from app.core.config import get_settings
from app.retrieval.base import Candidate
from app.retrieval.postgres import source_catalog
from app.security.scope import Scope
from app.services.conversation import conversation_only, source_aware_route


@pytest.mark.parametrize(
    "question",
    ["Hello!", "Remember my project codename.", "What codename did I give my personal project earlier?"],
)
def test_conversation_recall_skips_document_intent_provider(question):
    assert conversation_only(question)
    assert not conversation_only("Which gas does photosynthesis absorb?")


@pytest.mark.parametrize("payload", ["{}", '{"route":"SQL"}', '{"route":"HYBRID"}', "not json"])
async def test_intent_provider_cannot_grant_tool_access(payload):
    class Provider:
        async def complete(self, *args, **kwargs):
            return payload, None

    with pytest.raises((ValueError, TypeError)):
        await source_aware_route(Provider(), "Question", [])


async def test_topic_catalog_uses_authorized_current_chunks_and_not_bodies():
    captured = []

    class DB:
        async def execute(self, statement):
            captured.append(statement)
            return SimpleNamespace(all=lambda: [("Policy.md", "Procedure")])

    assert await source_catalog(DB(), Scope("tenant", "user", "EMPLOYEE")) == [
        {"document": "Policy.md", "section": "Procedure"}
    ]
    statement = str(captured[0])
    assert "documents.min_role <=" in statement and "document_chunks.version = documents.version" in statement
    assert "documents.status =" in statement and "document_chunks.tenant_id =" in statement
    assert "document_chunks.text" not in statement


@pytest.mark.parametrize("intent", ["DOCUMENT", "DIRECT", "unavailable", "rate_limited"])
async def test_workflow_source_intent_and_provider_failure_are_safe(monkeypatch, intent):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "generation_mode", "llm")
    monkeypatch.setattr(cfg, "guardrails_enabled", True)
    calls = []

    class Provider:
        async def stream(self, messages, **kwargs):
            instruction = messages[0]["content"]
            if instruction.startswith("Classify the user's intent"):
                calls.append("intent")
                if intent in {"unavailable", "rate_limited"}:
                    if intent == "rate_limited":
                        raise httpx.HTTPStatusError(
                            "private-rate-limit",
                            request=httpx.Request("POST", "https://invalid.test"),
                            response=httpx.Response(429),
                        )
                    raise httpx.ConnectError("private-provider-error")
                text = json.dumps({"route": intent})
            elif instruction.startswith("Compare the ANSWER"):
                text = '{"supported":true,"reason":"Evidence states the same value."}'
            else:
                calls.append("generation")
                text = (
                    "The answer is 30 days [Source 1]." if intent == "DOCUMENT" else "A general explanation."
                )
            yield {"text": text}

    class Retriever:
        def __init__(self, db):
            pass

        async def retrieve(self, question, scope):
            calls.append("retrieval")
            return (
                []
                if intent in {"unavailable", "rate_limited"}
                else [Candidate("c", "d", "Policy.md", "The answer is 30 days.", None, "Procedure", 1)]
            )

    class Ranker:
        async def rerank(self, question, candidates):
            return candidates[:6]

    class DB:
        async def execute(self, *args):
            raise AssertionError("Catalog is substituted below.")

        async def scalar(self, *args):
            return True

        async def rollback(self):
            calls.append("rollback")

    async def catalog(db, scope):
        return [{"document": "Policy.md", "section": "Procedure"}]

    async def emit(event, data):
        assert event != "draft"

    monkeypatch.setattr(workflow, "source_catalog", catalog)
    monkeypatch.setattr(workflow, "llm", Provider)
    monkeypatch.setattr(workflow, "DenseRetriever", Retriever)
    monkeypatch.setattr(workflow, "LexicalRetriever", Retriever)
    monkeypatch.setattr(workflow, "reranker", Ranker)
    result = await workflow.execute(DB(), Scope("tenant", "user", "EMPLOYEE"), "What happens next?", [], emit)
    if intent == "DIRECT":
        assert "retrieval" not in calls and result["route"] == "DIRECT"
    elif intent == "DOCUMENT":
        assert "retrieval" in calls and result["grounding"] == "SUPPORTED" and result["citations"]
    else:
        assert result["route"] == "DOCUMENT" and "retrieval" in calls
        assert "generation" not in calls and not result["citations"]
        assert "I couldn't confirm" in result["answer"]
        assert "private-provider-error" not in result["answer"]


async def test_human_review_sample_is_stratified_and_does_not_expose_prior_grades():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "human_packet", Path(__file__).resolve().parents[2] / "scripts/prepare_human_review.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    record = json.loads(
        (Path(__file__).resolve().parents[2] / "docs/evidence/answer-comparison.json").read_text()
    )
    result = module.packet(record)
    assert len(result["cards"]) == 20
    assert all("mode" not in card and "review" not in card for card in result["cards"])
    categories = {c["id"]: c["category"] for c in record["dataset"]["cases"]}
    lookup = {r["review_id"]: categories[r["case_id"]] for r in record["rows"]}
    from collections import Counter

    assert Counter(lookup[c["review_id"]] for c in result["cards"]) == {
        "answerable": 10,
        "unanswerable": 5,
        "followup": 5,
    }
