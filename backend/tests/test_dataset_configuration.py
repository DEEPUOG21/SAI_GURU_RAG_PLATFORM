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

def test_bundled_demo_labels_match_source_sections(monkeypatch):
    from pathlib import Path

    from app.evaluation import service

    demo = Path(__file__).resolve().parents[2] / "data" / "demo"
    monkeypatch.setattr(service, "DATASET", demo / "evaluation.json")
    cases = service.load_dataset()
    assert len(cases) == 8
    assert {name for case in cases for name in case["expected_documents"]} == {
        path.name for path in demo.glob("*.md")
    }
    for case in cases:
        for citation in case["expected_citations"]:
            content = (demo / citation["document"]).read_text(encoding="utf-8")
            assert "## " + citation["section"] in content.splitlines()


def test_container_data_directory_and_private_override(monkeypatch, tmp_path):
    import importlib

    demo = tmp_path / "demo"
    demo.mkdir()
    (demo / "evaluation.json").write_text("[]")
    try:
        with monkeypatch.context() as patch:
            patch.setenv("SAI_DATA_DIR", str(tmp_path))
            importlib.reload(service)
            assert service.DATASET == demo / "evaluation.json"
            (tmp_path / "evaluation.json").write_text("[]")
            importlib.reload(service)
            assert service.DATASET == tmp_path / "evaluation.json"
    finally:
        importlib.reload(service)
