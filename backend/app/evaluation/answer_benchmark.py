"""Answer benchmark validation and explicit, externally reviewed scoring."""

import hashlib
import json
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from statistics import mean

from app.agents import workflow
from app.evaluation.langsmith_export import experiment_payload
from app.evaluation.retrieval_benchmark import paired_deltas, percentile

MODES = ("dense_baseline", "current")


def load_answer_benchmark(path: Path, corpus: Path):
    raw = path.read_text(encoding="utf-8")
    dataset = json.loads(raw)
    cases = dataset["cases"]
    if Counter(c["category"] for c in cases) != {"answerable": 30, "unanswerable": 15, "followup": 15}:
        raise ValueError("Expected 30 answerable, 15 unanswerable and 15 follow-up targets.")
    if len({c["id"] for c in cases}) != 60 or len({c["question"].casefold() for c in cases}) != 60:
        raise ValueError("Case identities and target questions must be unique.")
    old = json.loads((corpus / "evaluation.json").read_text(encoding="utf-8"))
    known = {c["question"].strip().casefold() for c in old}
    for case in cases:
        if not case["question"].strip() or not case["expected_answer"].strip():
            raise ValueError("Missing question or written reference answer.")
        if case["question"].strip().casefold() in known:
            raise ValueError("Exact overlap with tuning questions.")
        if case["category"] == "followup" and not case.get("setup_question"):
            raise ValueError("Follow-up targets require a real setup turn.")
        for label in case["expected_sections"] + case.get("setup_expected_sections", []):
            name = label["document"]
            if Path(name).name != name or f"## {label['section']}\n" not in (corpus / name).read_text(
                encoding="utf-8"
            ):
                raise ValueError("Invalid source-section reference.")
    return dataset, hashlib.sha256(raw.encode("utf-8")).hexdigest()


@contextmanager
def retrieval_mode(mode):
    """Single-process experiment adapter; production guards, prompts and resolver stay fixed."""
    if mode not in MODES:
        raise ValueError("Unknown answer benchmark mode.")
    lexical, ranker = workflow.LexicalRetriever, workflow.reranker

    class EmptyLexical:
        def __init__(self, db):
            pass

        async def retrieve(self, question, scope):
            return []

    class DenseOrder:
        async def rerank(self, question, candidates, k=6):
            return candidates[:k]

    try:
        if mode == "dense_baseline":
            workflow.LexicalRetriever = EmptyLexical
            workflow.reranker = DenseOrder
        yield
    finally:
        workflow.LexicalRetriever, workflow.reranker = lexical, ranker


def attach_reviews(record, reviews):
    cases = {c["id"]: c for c in record["dataset"]["cases"]}
    expected = {r["review_id"] for r in record["rows"] if r["status"] == "COMPLETED"}
    if {r["review_id"] for r in reviews} != expected or len(reviews) != len(expected):
        raise ValueError("Every completed setup and target needs exactly one review.")
    lookup = {r["review_id"]: r for r in reviews}
    for row in record["rows"]:
        if row["status"] != "COMPLETED":
            continue
        review = lookup[row["review_id"]]
        case = cases[row["case_id"]]
        sections = (
            case.get("setup_expected_sections", []) if row["turn"] == "setup" else case["expected_sections"]
        )
        if sections and type(review.get("citation_supported")) is not bool:
            raise ValueError("Source-answerable reviews require explicit citation-support labels.")
        if not all(type(review.get(k)) is bool for k in ("correct", "unsupported_claim", "abstained")):
            raise ValueError("Review labels must be explicit booleans.")
        if (
            review.get("citation_supported") is not None
            and type(review.get("citation_supported")) is not bool
        ):
            raise ValueError("Citation support must be boolean or not applicable.")
        if not review.get("reason"):
            raise ValueError("Every review needs a source-based rationale.")
        row["review"] = review
    return record


def answer_summary(record):
    cases = {c["id"]: c for c in record["dataset"]["cases"]}
    summary = {}
    for mode in MODES:
        targets = [r for r in record["rows"] if r["mode"] == mode and r["turn"] == "target"]
        completed = [r for r in targets if r["status"] == "COMPLETED"]
        reviewed = [r for r in completed if "review" in r]
        bucket = {
            "targets_planned": 60,
            "attempted": len(targets),
            "completed": len(completed),
            "failed": len(targets) - len(completed),
            "reviewed": len(reviewed),
            "latency_p50_ms": percentile([r["latency_ms"] for r in completed], 0.5),
            "latency_p95_ms": percentile([r["latency_ms"] for r in completed], 0.95),
        }
        if len(reviewed) == 60:
            unknown = [r for r in reviewed if cases[r["case_id"]]["category"] == "unanswerable"]
            answerable = [r for r in reviewed if cases[r["case_id"]]["category"] != "unanswerable"]
            followups = [r for r in reviewed if cases[r["case_id"]]["category"] == "followup"]
            singles = [r for r in reviewed if cases[r["case_id"]]["category"] == "answerable"]
            source_answerable = [r for r in answerable if cases[r["case_id"]]["expected_sections"]]
            company = [r for r in reviewed if cases[r["case_id"]]["expected_sections"] or r in unknown]
            bucket["metrics"] = {
                "correctness": mean(r["review"]["correct"] for r in reviewed),
                "answerable_correctness": mean(r["review"]["correct"] for r in answerable),
                "single_turn_correctness": mean(r["review"]["correct"] for r in singles),
                "unknown_safe_abstention": mean(
                    r["review"]["abstained"] and not r["review"]["unsupported_claim"] for r in unknown
                ),
                "false_refusal_rate": mean(r["review"]["abstained"] for r in answerable),
                "followup_correctness": mean(r["review"]["correct"] for r in followups),
                "unsupported_company_answer_rate": mean(r["review"]["unsupported_claim"] for r in company),
                "source_question_citation_support": mean(
                    bool(r["review"]["citation_supported"]) for r in source_answerable
                ),
            }
            bucket["denominators"] = {
                "all": 60,
                "answerable_including_followups": len(answerable),
                "unknown": 15,
                "followup": 15,
                "source_answerable": len(source_answerable),
                "company": len(company),
            }
            bucket["source_questions_routed_direct"] = sum(
                r["route"] == "DIRECT" for r in source_answerable if "route" in r
            )
            setup_by_case = {
                r["case_id"]: r
                for r in record["rows"]
                if r["mode"] == mode and r["turn"] == "setup" and r.get("review")
            }
            if len(setup_by_case) == 15:
                bucket["metrics"]["conversation_pair_correctness"] = mean(
                    r["review"]["correct"] and setup_by_case[r["case_id"]]["review"]["correct"]
                    for r in followups
                )
        summary[mode] = bucket
    return summary


def answer_experiment_payload(record, name, mode):
    if mode not in MODES or not record.get("completed_at"):
        raise ValueError("Only completed answer experiments may be exported.")
    rows = [r for r in record["rows"] if r["mode"] == mode and r["turn"] == "target"]
    if len(rows) != 60 or any(r["status"] != "COMPLETED" or "review" not in r for r in rows):
        raise ValueError("Export requires 60 completed and reviewed target answers.")
    lookup = {c["id"]: c for c in record["dataset"]["cases"]}
    cases = []
    for row in rows:
        case, review = lookup[row["case_id"]], row["review"]
        question = (
            ("Conversation setup: " + case["setup_question"] + "\nLatest question: ")
            if case.get("setup_question")
            else ""
        ) + case["question"]
        metrics = {
            "correctness": float(review["correct"]),
            "unsupported_claim": float(review["unsupported_claim"]),
            "abstained": float(review["abstained"]),
            "latency_ms": row["latency_ms"],
        }
        if review["citation_supported"] is not None:
            metrics["citation_supported"] = float(review["citation_supported"])
        cases.append(
            {
                "question": question,
                "expected_answer": case["expected_answer"],
                "answer": row["answer"],
                "citations": row["citations"],
                "metrics": metrics,
            }
        )
    # Uniform summary keys are needed by the existing importer; N/A citation coverage is not averaged as zero.
    for case in cases:
        case["metrics"].pop("citation_supported", None)
    payload = experiment_payload(
        {
            "status": "COMPLETED",
            "id": record["created_at"] + ":" + mode,
            "created_at": record["created_at"],
            "results": {"cases": cases},
        },
        name,
    )
    payload["experiment_description"] = (
        "Imported frozen 60-case answer study; coding-agent review against source facts. Not independently human-annotated or LangSmith rescored. Display timeline reconstructed."
    )
    payload["experiment_metadata"].update(
        mode=mode,
        dataset_sha256=record["dataset_sha256"],
        methodology=record["methodology"],
        metric_notes="correctness, unsupported_claim and abstained are source-based coding-agent annotations, not generator grounding scores",
    )
    for output, row in zip(payload["results"], rows, strict=True):
        case, review = lookup[row["case_id"]], row["review"]
        output["run_metadata"].update(
            category=case["category"], case_id=case["id"], review_reason=review["reason"]
        )
        subset_scores = {}
        if case["category"] == "answerable":
            subset_scores["single_turn_correctness"] = float(review["correct"])
        if case["expected_sections"] or case["category"] == "unanswerable":
            subset_scores["unsupported_company_answer_rate"] = float(review["unsupported_claim"])
        if review["citation_supported"] is not None:
            subset_scores["citation_supported"] = float(review["citation_supported"])
        if case["category"] == "unanswerable":
            subset_scores["unknown_safe_abstention"] = float(
                review["abstained"] and not review["unsupported_claim"]
            )
        else:
            subset_scores["false_refusal"] = float(review["abstained"])
        if case["category"] == "followup":
            subset_scores["followup_correctness"] = float(review["correct"])
        output["evaluation_scores"].extend(
            {"key": key, "score": value} for key, value in subset_scores.items()
        )
        setup = next(
            (
                r
                for r in record["rows"]
                if r["case_id"] == row["case_id"] and r["mode"] == mode and r["turn"] == "setup"
            ),
            None,
        )
        if setup:
            output["actual_outputs"]["setup_answer"] = setup.get("answer")
            if setup.get("review"):
                output["evaluation_scores"].append(
                    {
                        "key": "conversation_pair_correctness",
                        "score": float(review["correct"] and setup["review"]["correct"]),
                    }
                )
    return payload


def paired_answer_comparisons(record):
    cases = {c["id"]: c for c in record["dataset"]["cases"]}
    cohorts = {
        "correctness": lambda c: True,
        "single_turn_correctness": lambda c: c["category"] == "answerable",
        "unknown_safe_abstention": lambda c: c["category"] == "unanswerable",
        "followup_correctness": lambda c: c["category"] == "followup",
        "false_refusal_rate": lambda c: c["category"] != "unanswerable",
        "unsupported_company_answer_rate": lambda c: (
            bool(c["expected_sections"]) or c["category"] == "unanswerable"
        ),
        "source_question_citation_support": lambda c: bool(c["expected_sections"]),
    }
    results = {}
    for metric, eligible in cohorts.items():
        rows = []
        for row in record["rows"]:
            case = cases[row["case_id"]]
            if (
                row["turn"] != "target"
                or row["status"] != "COMPLETED"
                or "review" not in row
                or not eligible(case)
            ):
                continue
            review = row["review"]
            value = (
                review["abstained"] and not review["unsupported_claim"]
                if metric == "unknown_safe_abstention"
                else review["abstained"]
                if metric == "false_refusal_rate"
                else review["unsupported_claim"]
                if metric == "unsupported_company_answer_rate"
                else bool(review["citation_supported"])
                if metric == "source_question_citation_support"
                else review["correct"]
            )
            rows.append(
                {
                    "case_id": row["case_id"],
                    "mode": row["mode"],
                    "status": "COMPLETED",
                    "repeat": 1,
                    "metrics": {metric: float(value)},
                }
            )
        results[metric] = paired_deltas(rows, "dense_baseline", "current")
    return results
