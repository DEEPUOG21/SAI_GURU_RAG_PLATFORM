"""Frozen, paired retrieval ablations; no generation, prompt tuning or database writes."""

import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from uuid import NAMESPACE_URL, uuid5

MODES = ("dense", "hybrid", "hybrid_reranked")


def load_benchmark(path: Path, corpus: Path):
    dataset = json.loads(path.read_text(encoding="utf-8"))
    cases = dataset["cases"]
    if len(cases) < 50 or len({row["id"] for row in cases}) != len(cases):
        raise ValueError("At least 50 uniquely identified cases are required.")
    if len({row["question"].strip().casefold() for row in cases}) != len(cases):
        raise ValueError("Duplicate benchmark questions.")
    original = json.loads((corpus / "evaluation.json").read_text(encoding="utf-8"))
    known = {row["question"].strip().casefold() for row in original}
    for row in cases:
        if not row["question"].strip() or row["question"].strip().casefold() in known:
            raise ValueError("Empty question or exact overlap with the tuning benchmark.")
        if not row["expected_sections"]:
            raise ValueError("Every retrieval case needs a source label.")
        for label in row["expected_sections"]:
            name, section = label["document"], label["section"]
            if Path(name).name != name:
                raise ValueError("Corpus filenames must be basenames.")
            source = (corpus / name).read_text(encoding="utf-8")
            if f"## {section}\n" not in source:
                raise ValueError(f"Unknown section: {name}: {section}")
    # Git normalizes text line endings. Keep the frozen identity stable across Windows and Linux.
    digest = hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(corpus.glob("*.md"))}
    return dataset, digest, hashes


def score_ranking(ranking, expected, k=6):
    """Score actual top-k chunks; duplicate section labels never earn extra credit."""
    labels = [(row["document"], row["section"]) for row in ranking[:k]]
    relevant = {(row["document"], row["section"]) for row in expected}
    if not relevant:
        raise ValueError("Cannot score retrieval without relevance labels.")
    seen = set()
    gains = []
    for label in labels:
        gains.append(int(label in relevant and label not in seen))
        seen.add(label)
    documents = {label[0] for label in relevant}
    ideal = sum(1 / math.log2(i + 2) for i in range(min(k, len(relevant))))
    return {
        "section_hit_at_1": float(bool(labels) and labels[0] in relevant),
        "section_recall_at_6": len(set(labels) & relevant) / len(relevant),
        "section_mrr_at_6": next((1 / (i + 1) for i, hit in enumerate(gains) if hit), 0.0),
        "section_ndcg_at_6": sum(hit / math.log2(i + 2) for i, hit in enumerate(gains)) / ideal,
        "document_recall_at_6": len({doc for doc, _ in labels} & documents) / len(documents),
    }


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    index = (len(ordered) - 1) * fraction
    low = math.floor(index)
    high = math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def summarize(rows):
    summary = {}
    for mode in MODES:
        runs = [row for row in rows if row["mode"] == mode]
        valid = [row for row in runs if row.get("status") == "COMPLETED"]
        metrics = (
            {key: mean(row["metrics"][key] for row in valid) for key in valid[0]["metrics"]} if valid else {}
        )
        latencies = [row["latency_ms"] for row in valid]
        summary[mode] = {
            "attempts": len(runs),
            "completed": len(valid),
            "errors": len(runs) - len(valid),
            "metrics": metrics,
            "latency_p50_ms": percentile(latencies, 0.5),
            "latency_p95_ms": percentile(latencies, 0.95),
        }
    return summary


def paired_deltas(rows, baseline="dense", treatment="hybrid_reranked", samples=2000):
    """Bootstrap question clusters, averaging repeats before resampling questions."""
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.get("status") == "COMPLETED":
            grouped[row["case_id"]][row["mode"]].append(row)
    pairs = []
    for modes in grouped.values():
        left = {r["repeat"]: r for r in modes[baseline]}
        right = {r["repeat"]: r for r in modes[treatment]}
        common = sorted(left.keys() & right.keys())
        if common:
            pairs.append({baseline: [left[i] for i in common], treatment: [right[i] for i in common]})
    if not pairs:
        return {"paired_cases": 0, "metrics": {}}
    result = {}
    for metric in pairs[0][baseline][0]["metrics"]:
        deltas = [
            mean(r["metrics"][metric] for r in modes[treatment])
            - mean(r["metrics"][metric] for r in modes[baseline])
            for modes in pairs
        ]
        rng = random.Random(20261027)
        draws = [mean(rng.choices(deltas, k=len(deltas))) for _ in range(samples)]
        result[metric] = {
            "mean_delta": mean(deltas),
            "ci95_low": percentile(draws, 0.025),
            "ci95_high": percentile(draws, 0.975),
            "wins": sum(d > 1e-12 for d in deltas),
            "ties": sum(abs(d) <= 1e-12 for d in deltas),
            "losses": sum(d < -1e-12 for d in deltas),
        }
    return {"baseline": baseline, "treatment": treatment, "paired_cases": len(pairs), "metrics": result}


def retrieval_experiment_payload(record, name, mode):
    """Export repeat-averaged measured rankings as one LangSmith example per question."""
    if mode not in MODES or not record.get("completed_at"):
        raise ValueError("Select a known mode from a completed retrieval benchmark.")
    grouped = defaultdict(list)
    for row in record["rows"]:
        if row["mode"] == mode:
            grouped[row["case_id"]].append(row)
    for case in record["dataset"]["cases"]:
        runs = grouped[case["id"]]
        if (
            len(runs) != record["repeats"]
            or any(r["status"] != "COMPLETED" for r in runs)
            or {r["repeat"] for r in runs} != set(range(1, record["repeats"] + 1))
        ):
            raise ValueError("Only complete modes with every planned repeat may be exported.")
    total_ms = sum(mean(r["latency_ms"] for r in runs) for runs in grouped.values())
    start = datetime.now(timezone.utc) - timedelta(milliseconds=total_ms)
    cursor = start
    dataset_id = uuid5(NAMESPACE_URL, "sai-guru-retrieval:" + record["dataset_sha256"])
    rows = []
    for case in record["dataset"]["cases"]:
        runs = sorted(grouped[case["id"]], key=lambda row: row["repeat"])
        scores = {key: mean(r["metrics"][key] for r in runs) for key in runs[0]["metrics"]}
        scores["latency_ms"] = mean(r["latency_ms"] for r in runs)
        end = cursor + timedelta(milliseconds=scores["latency_ms"])
        rows.append(
            {
                "row_id": str(uuid5(dataset_id, case["id"])),
                "inputs": {"question": case["question"]},
                "expected_outputs": {"expected_sections": case["expected_sections"]},
                "actual_outputs": {"mode": mode, "rankings_by_repeat": [r["ranking"] for r in runs]},
                "evaluation_scores": [{"key": k, "score": v} for k, v in scores.items()],
                "start_time": cursor.isoformat(),
                "end_time": end.isoformat(),
                "run_name": "Imported paired retrieval benchmark",
                "run_metadata": {
                    "imported": True,
                    "repeats": record["repeats"],
                    "category": case["category"],
                    "case_id": case["id"],
                    "timing": "Reconstructed offsets from mean measured component duration",
                },
            }
        )
        cursor = end
    return {
        "experiment_name": name,
        "experiment_description": "Imported frozen retrieval comparison; repeat-averaged scores, no generation or LangSmith rescoring. Display timing reconstructed.",
        "experiment_start_time": start.isoformat(),
        "experiment_end_time": cursor.isoformat(),
        "dataset_name": "Sai Guru retrieval " + record["dataset_sha256"][:12],
        "experiment_metadata": {
            "source_run_id": record["created_at"] + ":" + mode,
            "dataset_fingerprint": record["dataset_sha256"],
            "chunk_snapshot_sha256": record["chunk_snapshot_sha256"],
            "mode": mode,
            "repeats": record["repeats"],
            "imported": True,
            "timing_reconstructed": True,
            "methodology": record["methodology"],
            "original_created_at": record["created_at"],
        },
        "summary_experiment_scores": [
            {
                "key": key,
                "score": mean(
                    next(s["score"] for s in r["evaluation_scores"] if s["key"] == key) for r in rows
                ),
            }
            for key in [s["key"] for s in rows[0]["evaluation_scores"]]
        ],
        "results": rows,
    }
