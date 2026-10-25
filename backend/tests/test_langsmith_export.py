from copy import deepcopy
from datetime import datetime

import pytest

from app.evaluation.langsmith_export import experiment_payload


def record():
    return {
        "run_id": "original",
        "status": "COMPLETED",
        "created_at": "2026-10-23T12:00:00+00:00",
        "cases": [
            {
                "question": "q",
                "expected_answer": "reference",
                "answer": "answer",
                "metrics": {"latency_ms": 1234, "answer_relevance": 0.5},
                "trace": {"private": "must not export"},
            }
        ],
    }


def test_same_dataset_matches_rows_across_experiments():
    before = record()
    after = deepcopy(before)
    after["cases"][0]["answer"] = "improved"
    a, b = experiment_payload(before, "before"), experiment_payload(after, "after")
    assert a["dataset_name"] == b["dataset_name"]
    assert a["results"][0]["row_id"] == b["results"][0]["row_id"]
    assert "private" not in str(a)
    row = a["results"][0]
    assert (
        datetime.fromisoformat(row["end_time"]) - datetime.fromisoformat(row["start_time"])
    ).total_seconds() == 1.234
    assert a["experiment_metadata"]["timing_reconstructed"] is True
    assert a["experiment_metadata"]["original_created_at"] == before["created_at"]
    after["cases"][0]["expected_answer"] = "changed reference"
    assert experiment_payload(after, "changed")["dataset_name"] != a["dataset_name"]


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_latency_rejected(value):
    data = record()
    data["cases"][0]["metrics"]["latency_ms"] = value
    with pytest.raises(ValueError):
        experiment_payload(data, "bad")


def test_incomplete_run_rejected():
    data = record()
    data["status"] = "RUNNING"
    with pytest.raises(ValueError):
        experiment_payload(data, "bad")


def test_feedback_precision_matches_hosted_api():
    data = record()
    data["cases"][0]["metrics"]["answer_relevance"] = 1 / 3
    payload = experiment_payload(data, "precision")
    scores = payload["summary_experiment_scores"] + payload["results"][0]["evaluation_scores"]
    assert all(score["score"] == round(score["score"], 4) for score in scores)


def test_sdk_import_preserves_references_and_metrics():
    from types import SimpleNamespace
    from uuid import uuid4

    from langsmith.utils import LangSmithNotFoundError

    from app.evaluation.langsmith_export import upload_experiment

    class Client:
        def __init__(self):
            self.dataset = SimpleNamespace(id=uuid4())
            self.project = SimpleNamespace(id=uuid4(), name="test")
            self.runs, self.feedback, self.examples = [], [], []

        def read_dataset(self, **kwargs):
            return self.dataset

        def list_examples(self, **kwargs):
            return []

        def create_example(self, **kwargs):
            self.examples.append(kwargs)

        def read_project(self, **kwargs):
            raise LangSmithNotFoundError("Not found")

        def create_project(self, **kwargs):
            assert kwargs["reference_dataset_id"] == self.dataset.id
            return self.project

        def create_run(self, **kwargs):
            self.runs.append(kwargs)

        def create_feedback(self, **kwargs):
            self.feedback.append(kwargs)

        def update_project(self, **kwargs):
            pass

    client = Client()
    payload = experiment_payload(record(), "test")
    upload_experiment(client, payload)
    assert len(client.examples) == len(client.runs) == 1
    assert client.runs[0]["reference_example_id"] == client.examples[0]["example_id"]
    assert client.runs[0]["outputs"] == {"answer": "answer"}
    assert {item["key"] for item in client.feedback} == {"latency_ms", "answer_relevance"}
    assert all(item["session_id"] == client.project.id for item in client.feedback)
