import json

import pytest

from app.evaluation import service


def test_missing_dataset_is_actionable(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "DATASET", tmp_path / "evaluation.json")
    with pytest.raises(ValueError, match="No evaluation dataset configured"):
        service.load_dataset()


@pytest.mark.parametrize(
    "content",
    [
        [],
        {},
        [{"question": "Q"}],
        [{"question": 1, "expected_answer": "A", "expected_documents": [], "expected_citations": []}],
    ],
)
def test_invalid_dataset_rejected(tmp_path, monkeypatch, content):
    path = tmp_path / "evaluation.json"
    path.write_text(json.dumps(content))
    monkeypatch.setattr(service, "DATASET", path)
    with pytest.raises(ValueError):
        service.load_dataset()


def test_custom_dataset_loads(tmp_path, monkeypatch):
    cases = [
        {
            "question": "Q",
            "expected_answer": "A",
            "expected_documents": ["policy.txt"],
            "expected_citations": [{"document": "policy.txt", "section": "Policy"}],
        }
    ]
    path = tmp_path / "evaluation.json"
    path.write_text(json.dumps(cases))
    monkeypatch.setattr(service, "DATASET", path)
    assert service.load_dataset() == cases
