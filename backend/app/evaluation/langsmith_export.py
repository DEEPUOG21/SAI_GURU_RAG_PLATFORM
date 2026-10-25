"""Prepare existing, measured evaluation results for LangSmith's import API."""

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5


def experiment_payload(record, name):
    results = record.get("results", record)
    if record.get("status") != "COMPLETED" or not results.get("cases"):
        raise ValueError("Only completed, nonempty evaluation runs can be exported.")
    cases = results["cases"]
    references = [{"question": c["question"], "expected_answer": c["expected_answer"]} for c in cases]
    fingerprint = hashlib.sha256(json.dumps(references, sort_keys=True).encode()).hexdigest()
    dataset_id = uuid5(NAMESPACE_URL, "sai-guru-evaluation:" + fingerprint)
    original_start = datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))
    for case in cases:
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in case["metrics"].values()):
            raise ValueError("Evaluation metrics must be finite numbers.")
        if case["metrics"]["latency_ms"] < 0:
            raise ValueError("Latency must be nonnegative.")
    # LangSmith rejects historical create_run timestamps. Keep provenance separate
    # and reconstruct only the display timeline, preserving measured durations.
    start = datetime.now(UTC) - timedelta(milliseconds=sum(c["metrics"]["latency_ms"] for c in cases))
    cursor = start
    rows = []
    for case in cases:
        metrics = case["metrics"]
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in metrics.values()):
            raise ValueError("Evaluation metrics must be finite numbers.")
        latency = metrics["latency_ms"]
        if latency < 0:
            raise ValueError("Latency must be nonnegative.")
        end = cursor + timedelta(milliseconds=latency)
        rows.append(
            {
                "row_id": str(uuid5(dataset_id, case["question"])),
                "inputs": {"question": case["question"]},
                "expected_outputs": {"answer": case["expected_answer"]},
                "actual_outputs": {"answer": case["answer"]},
                "evaluation_scores": [{"key": k, "score": round(v, 4)} for k, v in metrics.items()],
                "start_time": cursor.isoformat(),
                "end_time": end.isoformat(),
                "run_name": "Imported Sai Guru evaluation case",
                "run_metadata": {"timing": "Reconstructed sequential offsets from measured latency_ms"},
            }
        )
        cursor = end
    if len({row["row_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate benchmark questions are not supported by this importer.")
    return {
        "experiment_name": name,
        "experiment_description": "Imported recorded results; no new inference or rescoring. Timelines reconstructed from measured case durations.",
        "experiment_start_time": start.isoformat(),
        "experiment_end_time": cursor.isoformat(),
        "dataset_name": "Sai Guru " + fingerprint[:12],
        "experiment_metadata": {
            "source_run_id": record.get("run_id", record.get("id")),
            "original_created_at": original_start.isoformat(),
            "imported": True,
            "dataset_fingerprint": fingerprint,
            "timing_reconstructed": True,
            "metric_notes": "answer_relevance is token-set F1; faithfulness is a fallible grounding judge; citation_correctness is exact label matching",
        },
        "summary_experiment_scores": [
            {"key": key, "score": round(sum(c["metrics"][key] for c in cases) / len(cases), 4)}
            for key in cases[0]["metrics"]
        ],
        "results": rows,
    }


def upload_experiment(client, payload):
    """Import through SDK primitives, preserving durations and reference rows."""
    from concurrent.futures import ThreadPoolExecutor

    from langsmith.utils import LangSmithNotFoundError

    name = payload["dataset_name"]
    try:
        dataset = client.read_dataset(dataset_name=name)
    except LangSmithNotFoundError:
        dataset = client.create_dataset(
            dataset_name=name, description="Sai Guru recorded synthetic benchmark"
        )
    existing = {str(example.id) for example in client.list_examples(dataset_id=dataset.id)}
    for row in payload["results"]:
        if row["row_id"] not in existing:
            client.create_example(
                dataset_id=dataset.id,
                example_id=row["row_id"],
                inputs=row["inputs"],
                outputs=row["expected_outputs"],
            )
    try:
        project = client.read_project(project_name=payload["experiment_name"])
    except LangSmithNotFoundError:
        project = client.create_project(
            project_name=payload["experiment_name"],
            reference_dataset_id=dataset.id,
            description=payload["experiment_description"],
            metadata=payload["experiment_metadata"],
        )
    else:
        old_metadata = (project.extra or {}).get("metadata", {})
        matches = old_metadata.get("source_run_id") == payload["experiment_metadata"]["source_run_id"]
        if not matches or list(client.list_runs(project_name=project.name, limit=1)):
            raise ValueError(
                "Experiment already contains runs or belongs to another source. Inspect it before retrying."
            )
        client.update_project(project_id=project.id, metadata=payload["experiment_metadata"])
    feedback = []
    for row in payload["results"]:
        run_id = uuid5(project.id, row["row_id"])
        client.create_run(
            id=run_id,
            name=row["run_name"],
            run_type="chain",
            project_name=project.name,
            inputs=row["inputs"],
            outputs=row["actual_outputs"],
            reference_example_id=row["row_id"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]),
            extra={"metadata": row["run_metadata"]},
        )
        feedback.extend((run_id, score) for score in row["evaluation_scores"])

    def send_feedback(item):
        run_id, score = item
        client.create_feedback(run_id=run_id, session_id=project.id, key=score["key"], score=score["score"])

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(send_feedback, feedback))
    client.update_project(
        project_id=project.id, end_time=datetime.fromisoformat(payload["experiment_end_time"])
    )
    return {"dataset_id": str(dataset.id), "project_id": str(project.id), "project_name": project.name}
