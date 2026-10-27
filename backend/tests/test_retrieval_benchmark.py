import json
from pathlib import Path

import pytest

from app.evaluation.retrieval_benchmark import (
    load_benchmark,
    paired_deltas,
    retrieval_experiment_payload,
    score_ranking,
    summarize,
)


def label(document="a.md", section="A"):
    return {"document": document, "section": section}


def test_section_labels_distinguish_wrong_section_in_right_document():
    scores = score_ranking([label(section="B")], [label()])
    assert scores["document_recall_at_6"] == 1
    assert scores["section_recall_at_6"] == scores["section_mrr_at_6"] == 0


def test_duplicate_sections_do_not_inflate_recall_or_ndcg():
    scores = score_ranking([label(), label(), label(section="B")], [label(), label(section="B")])
    assert scores["section_recall_at_6"] == 1
    assert 0 < scores["section_ndcg_at_6"] < 1


def test_top_k_cutoff_is_applied_before_deduplication():
    scores = score_ranking([label(section="B")] * 6 + [label()], [label()])
    assert scores["section_recall_at_6"] == 0


def test_partial_multihop_recall_and_first_relevant_rank():
    scores = score_ranking([label(section="other"), label()], [label(), label("b.md")])
    assert scores["section_hit_at_1"] == 0
    assert scores["section_recall_at_6"] == 0.5
    assert scores["section_mrr_at_6"] == 0.5


def row(mode, value, repeat=1, case="one"):
    return {
        "case_id": case,
        "mode": mode,
        "repeat": repeat,
        "status": "COMPLETED",
        "metrics": {"mrr": value},
        "latency_ms": 10,
    }


def test_paired_intervals_average_repeats_and_cluster_by_question():
    rows = [row("dense", 0.5, i) for i in range(1, 4)] + [row("hybrid_reranked", 1, i) for i in range(1, 4)]
    result = paired_deltas(rows, samples=100)
    assert result["paired_cases"] == 1
    assert result["metrics"]["mrr"]["ci95_low"] == 0.5
    assert result["metrics"]["mrr"]["ci95_high"] == 0.5


def test_failed_repeats_are_excluded_from_both_sides_of_a_pair():
    rows = [
        row("dense", 0.5),
        row("hybrid_reranked", 0.5),
        row("dense", 1, 2),
        {"case_id": "one", "mode": "hybrid_reranked", "repeat": 2, "status": "FAILED"},
    ]
    assert paired_deltas(rows, samples=100)["metrics"]["mrr"]["mean_delta"] == 0
    summary = summarize(rows)
    assert summary["hybrid_reranked"]["errors"] == 1
    assert summary["hybrid_reranked"]["completed"] == 1


def test_frozen_dataset_has_valid_labels_and_no_exact_tuning_overlap():
    corpus = Path(__file__).resolve().parents[2] / "data/demo"
    dataset, digest, hashes = load_benchmark(corpus / "retrieval-holdout.json", corpus)
    assert len(dataset["cases"]) == 56
    assert len(digest) == 64 and len(hashes) == 8
    assert sum(c["category"] == "cross_document" for c in dataset["cases"]) == 8


def test_dataset_rejects_unknown_sections(tmp_path):
    corpus = Path(__file__).resolve().parents[2] / "data/demo"
    data = json.loads((corpus / "retrieval-holdout.json").read_text())
    data["cases"][0]["expected_sections"][0]["section"] = "Invented section"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Unknown section"):
        load_benchmark(path, corpus)


def test_dataset_fingerprint_survives_git_line_ending_normalization(tmp_path):
    corpus = Path(__file__).resolve().parents[2] / "data/demo"
    source = (corpus / "retrieval-holdout.json").read_text(encoding="utf-8")
    lf, crlf = tmp_path / "lf.json", tmp_path / "crlf.json"
    lf.write_bytes(source.encode("utf-8"))
    crlf.write_bytes(source.replace("\n", "\r\n").encode("utf-8"))
    assert load_benchmark(lf, corpus)[1] == load_benchmark(crlf, corpus)[1]


def export_record():
    rows = [row(mode, value, repeat) for mode, value in [("dense", 0.5), ("hybrid", 1)] for repeat in [1, 2]]
    for r in rows:
        r["ranking"] = [label()]
    return {
        "created_at": "2026-10-27T00:00:00+00:00",
        "completed_at": "2026-10-27T00:01:00+00:00",
        "dataset_sha256": "a" * 64,
        "chunk_snapshot_sha256": "b" * 64,
        "repeats": 2,
        "methodology": {},
        "rows": rows,
        "dataset": {
            "cases": [
                {
                    "id": "one",
                    "question": "Which section?",
                    "category": "single_section",
                    "expected_sections": [label()],
                }
            ]
        },
    }


def test_langsmith_modes_share_examples_and_preserve_measured_repeat_averages():
    record = export_record()
    dense = retrieval_experiment_payload(record, "dense-exp", "dense")
    hybrid = retrieval_experiment_payload(record, "hybrid-exp", "hybrid")
    assert dense["dataset_name"] == hybrid["dataset_name"]
    assert dense["results"][0]["row_id"] == hybrid["results"][0]["row_id"]
    assert dense["results"][0]["evaluation_scores"][0] == {"key": "mrr", "score": 0.5}
    assert len(hybrid["results"][0]["actual_outputs"]["rankings_by_repeat"]) == 2
    assert hybrid["experiment_metadata"]["imported"] is True


def test_langsmith_export_rejects_incomplete_repeats():
    record = export_record()
    record["rows"].pop()
    with pytest.raises(ValueError, match="every planned repeat"):
        retrieval_experiment_payload(record, "hybrid-exp", "hybrid")
