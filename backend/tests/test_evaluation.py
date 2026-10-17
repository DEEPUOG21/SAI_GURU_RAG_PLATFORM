import pytest

from app.evaluation.metrics import citation_correctness, retrieval_metrics, token_f1


def test_retrieval_regression_fixture():
    metrics = retrieval_metrics(["other", "leave", "leave", "security"], ["leave", "security"], k=3)
    assert metrics["recall_at_k"] == 1
    assert metrics["precision_at_k"] == pytest.approx(2 / 3)
    assert metrics["mrr"] == 0.5
    assert metrics["ndcg"] == pytest.approx(0.6934264036)


def test_missing_results_penalized():
    metrics = retrieval_metrics([], ["leave"])
    assert all(value == 0 for value in metrics.values())
    assert retrieval_metrics(["leave"], ["leave"], 6)["precision_at_k"] == pytest.approx(1 / 6)


def test_generation_metrics():
    assert token_f1("24 annual days", "24 annual days") == 1
    assert token_f1("irrelevant", "24 days") == 0
    assert (
        citation_correctness(
            [{"document": "Leave.md", "section": "Leave"}], [{"document": "Leave.md", "section": "Leave"}]
        )
        == 1
    )
    assert citation_correctness([], []) == 0
