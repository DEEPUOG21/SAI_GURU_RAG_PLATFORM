import pytest

from app.agents.routing import classify, rewrite
from app.agents.sql import SQL_TEMPLATES, generate_sql, validate_sql
from app.observability.trace import Trace
from app.services.grounding import check_grounding, citations_valid


@pytest.mark.parametrize(
    "query,route",
    [
        ("What is our leave policy?", "DOCUMENT"),
        ("How many employees joined last month?", "SQL"),
        ("Compare employee growth with our hiring policy.", "HYBRID"),
        ("What is RAG?", "DIRECT"),
        ("hi", "DIRECT"),
        ("Hello!", "DIRECT"),
        ("Hey Sai Guru", "DIRECT"),
        ("Good morning", "DIRECT"),
        ("How are you?", "DIRECT"),
        ("Thank you", "DIRECT"),
        ("Hi, what is our leave policy?", "DOCUMENT"),
        ("Hi, how many employees joined last month?", "SQL"),
        ("how is the father of the nation?", "DIRECT"),
        ("Who is the father of the nation in India?", "DIRECT"),
        ("What is Python?", "DIRECT"),
        ("What is 2 + 2?", "DIRECT"),
        ("Explain photosynthesis", "DIRECT"),
        ("Write a short poem", "DIRECT"),
        ("What does our company do?", "DOCUMENT"),
        ("Summarize the uploaded file", "DOCUMENT"),
        ("How do I claim expenses?", "DOCUMENT"),
        ("What is the SEV1 acknowledgement target?", "DOCUMENT"),
        ("Which reviewer is required for changes to authentication code?", "DOCUMENT"),
        ("How long do Atlas data export download links remain valid?", "DOCUMENT"),
        ("Who approves a production pull request?", "DOCUMENT"),
        ("Can a workspace viewer change tasks?", "DOCUMENT"),
        ("What is authentication?", "DIRECT"),
    ],
)
def test_routes(query, route):
    assert classify(query) == route


def test_rewrite_followup():
    assert "leave" in rewrite("Does it cover contractors?", [{"role": "user", "content": "Explain leave"}])


def test_followup_routes_with_previous_topic():
    assert (
        classify(rewrite("Tell me more", [{"role": "user", "content": "Explain our leave policy"}]))
        == "DOCUMENT"
    )
    assert classify(rewrite("Tell me more", [{"role": "user", "content": "What is Python?"}])) == "DIRECT"
    assert (
        classify(rewrite("When was he born?", [{"role": "user", "content": "Who was Gandhi?"}])) == "DIRECT"
    )


def test_numeric_policy_question_is_not_employee_analytics():
    assert classify("How many paid annual leave days do full-time SaiTech employees receive?") == "DOCUMENT"


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM employees",
        "SELECT * FROM users",
        "SELECT pg_sleep(100)",
        "SELECT * FROM employee_analytics; DROP TABLE users",
        "SELECT * INTO x FROM employee_analytics",
        "WITH x AS (DELETE FROM users RETURNING *) SELECT * FROM x",
    ],
)
def test_sql_rejects_unsafe_statements(sql):
    with pytest.raises(ValueError):
        validate_sql(sql)


def test_sql_templates():
    for sql in SQL_TEMPLATES.values():
        assert "LIMIT 100" in validate_sql(sql)
    assert generate_sql("How many employees joined last month?") == SQL_TEMPLATES["last_month"]
    with pytest.raises(ValueError):
        generate_sql("show all salaries")


def test_citations():
    context = [{"label": "Source 1"}]
    assert citations_valid("24 days [Source 1]", context)
    assert not citations_valid("24 days [Source 2]", context)
    assert not citations_valid("24 days", context)


async def test_grounding_rejects_malformed_judge():
    class Judge:
        async def complete(self, *args, **kwargs):
            return "not json", None

    verdict, _ = await check_grounding(
        Judge(),
        "q",
        "claim [Source 1]",
        [{"label": "Source 1", "document": "d", "section": "s", "text": "evidence"}],
    )
    assert verdict["status"] == "UNSUPPORTED"


async def test_retries_are_bounded():
    trace, calls = Trace(), []

    async def fail():
        calls.append(1)
        raise ValueError("failure")

    with pytest.raises(ValueError):
        await trace.run("test", fail, retries=1)
    assert len(calls) == 2 and trace.steps[0]["status"] == "failed"
    for _ in range(23):
        trace.record("node", None)
    with pytest.raises(RuntimeError):
        trace.record("node", None)


async def test_grounding_rejects_invented_number_before_judge():
    class Judge:
        async def complete(self, *args, **kwargs):
            raise AssertionError("Invented numbers must be rejected before model judgment")

    context = [{"label": "Source 1", "text": "Employees receive 24 days of annual leave."}]
    verdict, usage = await check_grounding(Judge(), "Annual leave", "99 days [Source 1]", context)
    assert verdict["status"] == "UNSUPPORTED" and usage is None


async def test_grounding_normalizes_numbers_and_ignores_citation_numbers():
    class Judge:
        async def complete(self, *args, **kwargs):
            return '{"supported": true}', None

    context = [{"label": "Source 2", "document": "d", "section": "s", "text": "The limit is 1,000 units."}]
    verdict, _ = await check_grounding(Judge(), "Limit", "1000.0 units [Source 2]", context)
    assert verdict["status"] == "SUPPORTED"


async def test_usage_tracking_preserves_missing_call_reports():
    from app.services.llm import TrackedLLM

    class Provider:
        async def stream(self, messages, **kwargs):
            yield {"text": "answer", "usage": messages[0].get("usage")}

    provider = TrackedLLM(Provider())
    await provider.complete([{"usage": {"total_tokens": 10}}])
    await provider.complete([{}])
    assert provider.usages == [{"total_tokens": 10}, None]
