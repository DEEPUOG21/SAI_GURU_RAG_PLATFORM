from pathlib import Path

import pytest

from app.agents import workflow
from app.evaluation.answer_benchmark import (
    MODES,
    answer_experiment_payload,
    answer_summary,
    attach_reviews,
    load_answer_benchmark,
    paired_answer_comparisons,
    retrieval_mode,
)


def dataset():
    corpus = Path(__file__).resolve().parents[2] / "data/demo"
    return load_answer_benchmark(corpus / "answer-holdout.json", corpus)


def test_frozen_answer_cohorts_and_sources_validate():
    data, digest = dataset()
    assert len(data["cases"]) == 60 and len(digest) == 64
    assert sum("setup_question" in c for c in data["cases"]) == 15
    assert sum(bool(c["expected_sections"]) for c in data["cases"]) == 42


@pytest.mark.asyncio
async def test_baseline_changes_only_lexical_and_reranking_and_restores_on_error():
    original = workflow.LexicalRetriever, workflow.reranker
    dense, generator, guards = workflow.DenseRetriever, workflow.llm, workflow.inspect
    with pytest.raises(RuntimeError, match="stop"):
        with retrieval_mode("dense_baseline"):
            assert await workflow.LexicalRetriever(None).retrieve("question", None) == []
            assert await workflow.reranker().rerank("question", list(range(8))) == list(range(6))
            assert (workflow.DenseRetriever, workflow.llm, workflow.inspect) == (dense, generator, guards)
            raise RuntimeError("stop")
    assert (workflow.LexicalRetriever, workflow.reranker) == original
    with retrieval_mode("current"):
        assert (workflow.LexicalRetriever, workflow.reranker) == original


def record_and_reviews():
    data, digest = dataset()
    rows, reviews = [], []
    for mode in MODES:
        for case in data["cases"]:
            rid = mode + case["id"]
            rows.append(
                {
                    "case_id": case["id"],
                    "mode": mode,
                    "turn": "target",
                    "review_id": rid,
                    "status": "COMPLETED",
                    "answer": "Fixture answer",
                    "citations": [],
                    "latency_ms": 100,
                }
            )
            reviews.append(
                {
                    "review_id": rid,
                    "correct": True,
                    "unsupported_claim": False,
                    "abstained": case["category"] == "unanswerable",
                    "citation_supported": True if case["expected_sections"] else None,
                    "reason": "Fixture explicitly matches its written reference.",
                }
            )
    return {
        "dataset": data,
        "dataset_sha256": digest,
        "rows": rows,
        "created_at": "2026-10-27T00:00:00+00:00",
        "completed_at": "2026-10-27T00:01:00+00:00",
        "methodology": {},
    }, reviews


def test_refusal_and_unsupported_rates_use_the_correct_eligible_cohorts():
    record, reviews = record_and_reviews()
    reviews[60].update(correct=False, abstained=True, citation_supported=False)
    reviews[90].update(correct=False, unsupported_claim=True, abstained=False)
    summary = answer_summary(attach_reviews(record, reviews))
    current = summary["current"]
    assert current["metrics"]["false_refusal_rate"] == 1 / 45
    assert current["metrics"]["unsupported_company_answer_rate"] == 1 / 57
    assert current["metrics"]["unknown_safe_abstention"] == 14 / 15
    assert current["metrics"]["source_question_citation_support"] == 41 / 42
    assert summary["dense_baseline"]["metrics"]["correctness"] == 1


def test_missing_reviews_never_silently_count_as_correct():
    record, reviews = record_and_reviews()
    with pytest.raises(ValueError, match="exactly one review"):
        attach_reviews(record, reviews[:-1])


def test_non_boolean_reviews_are_rejected():
    record, reviews = record_and_reviews()
    reviews[0]["correct"] = "yes"
    with pytest.raises(ValueError, match="explicit booleans"):
        attach_reviews(record, reviews)


def test_source_citation_support_cannot_be_marked_not_applicable():
    record, reviews = record_and_reviews()
    reviews[0]["citation_supported"] = None
    with pytest.raises(ValueError, match="explicit citation-support"):
        attach_reviews(record, reviews)


def test_export_keeps_subset_feedback_out_of_ineligible_cases_and_shares_examples():
    record, reviews = record_and_reviews()
    attach_reviews(record, reviews)
    left = answer_experiment_payload(record, "baseline", "dense_baseline")
    right = answer_experiment_payload(record, "current", "current")
    assert left["dataset_name"] == right["dataset_name"]
    assert [r["row_id"] for r in left["results"]] == [r["row_id"] for r in right["results"]]
    scores = [[s["key"] for s in r["evaluation_scores"]] for r in right["results"]]
    assert sum("false_refusal" in r for r in scores) == 45
    assert sum("unknown_safe_abstention" in r for r in scores) == 15
    assert sum("citation_supported" in r for r in scores) == 42
    assert sum("followup_correctness" in r for r in scores) == 15


def test_export_rejects_partial_trials():
    record, reviews = record_and_reviews()
    attach_reviews(record, reviews)
    record["rows"][0]["status"] = "FAILED"
    with pytest.raises(ValueError, match="60 completed and reviewed"):
        answer_experiment_payload(record, "baseline", "dense_baseline")


def test_paired_comparisons_keep_cohort_denominators_and_do_not_pool_setup_turns():
    record, reviews = record_and_reviews()
    attach_reviews(record, reviews)
    comparisons = paired_answer_comparisons(record)
    assert comparisons["correctness"]["paired_cases"] == 60
    assert comparisons["unknown_safe_abstention"]["paired_cases"] == 15
    assert comparisons["followup_correctness"]["paired_cases"] == 15
    assert comparisons["source_question_citation_support"]["paired_cases"] == 42
    assert comparisons["false_refusal_rate"]["paired_cases"] == 45
    assert comparisons["correctness"]["metrics"]["correctness"]["mean_delta"] == 0
