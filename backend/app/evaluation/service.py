import asyncio
import hashlib
import json
from pathlib import Path

from sqlalchemy import select

from app.agents.workflow import execute
from app.core.config import get_settings
from app.database.session import Session
from app.evaluation.metrics import citation_correctness, retrieval_metrics, token_f1
from app.models.entities import Evaluation

DATASET = Path(__file__).resolve().parents[3] / "data" / "evaluation.json"
if not DATASET.is_file():
    DATASET = DATASET.parent / "demo" / "evaluation.json"


def load_dataset():
    if not DATASET.is_file():
        raise ValueError("No evaluation dataset configured. Ask your administrator to add a labeled dataset.")
    cases = json.loads(DATASET.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("The evaluation dataset must contain at least one labeled question.")
    required = {"question", "expected_answer", "expected_documents", "expected_citations"}
    if any(not isinstance(case, dict) or not required.issubset(case) for case in cases):
        raise ValueError("The evaluation dataset is missing required labels.")
    for case in cases:
        if not all(
            isinstance(case[key], str) and case[key].strip() for key in ("question", "expected_answer")
        ):
            raise ValueError("Evaluation questions and answers must be nonempty strings.")
        if not isinstance(case["expected_documents"], list) or not all(
            isinstance(name, str) for name in case["expected_documents"]
        ):
            raise ValueError("Expected documents must be a list of filenames.")
        if not isinstance(case["expected_citations"], list) or not all(
            isinstance(citation, dict)
            and all(isinstance(citation.get(key), str) for key in ("document", "section"))
            for citation in case["expected_citations"]
        ):
            raise ValueError("Expected citations must contain document and section labels.")
    return cases


async def run_evaluation(scope, cases):
    version = hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()[:16]
    async with Session(scope=scope) as db:
        evaluation = Evaluation(tenant_id=scope.tenant_id, user_id=scope.user_id, dataset_version=version)
        db.add(evaluation)
        await db.commit()
        id = evaluation.id
    rows = []

    async def discard(event, data):
        pass

    try:
        async with asyncio.timeout(600):
            for case in cases:
                async with Session(scope=scope) as db:
                    result = await execute(db, scope, case["question"], [], discard)
                citations = result["citations"]
                metrics = retrieval_metrics(
                    [c.document for c in result["candidates"]], case["expected_documents"]
                )
                metrics.update(
                    {
                        "faithfulness": 1.0 if result["grounding"] == "SUPPORTED" else 0.0,
                        "answer_relevance": token_f1(result["answer"], case["expected_answer"]),
                        "context_relevance": sum(
                            c.document in case["expected_documents"] for c in result["candidates"]
                        )
                        / max(1, len(result["candidates"])),
                        "citation_correctness": citation_correctness(citations, case["expected_citations"]),
                        "latency_ms": result["latency_ms"],
                    }
                )
                rows.append(
                    {
                        "question": case["question"],
                        "expected_answer": case["expected_answer"],
                        "answer": result["answer"],
                        "citations": citations,
                        "metrics": metrics,
                        "token_usage": result["token_usage"],
                        "estimated_cost": result["estimated_cost"],
                        "trace": result["trace"],
                    }
                )
        status, error = "COMPLETED", None
    except (Exception, asyncio.CancelledError) as exc:
        status, error = "FAILED", type(exc).__name__
    async with Session(scope=scope) as db:
        evaluation = await db.get(Evaluation, id)
        evaluation.status = status
        aggregate = (
            {key: sum(row["metrics"][key] for row in rows) / len(rows) for key in rows[0]["metrics"]}
            if rows
            else {}
        )
        previous = await db.scalar(
            select(Evaluation)
            .where(
                Evaluation.tenant_id == scope.tenant_id,
                Evaluation.user_id == scope.user_id,
                Evaluation.id != id,
                Evaluation.status == "COMPLETED",
                Evaluation.dataset_version == version,
            )
            .order_by(Evaluation.created_at.desc())
            .limit(1)
        )
        evaluation.results = {
            "configuration": {
                key: getattr(get_settings(), key)
                for key in (
                    "generation_mode",
                    "embedding_model",
                    "reranker_model",
                    "llm_model",
                    "grounding_action",
                )
            },
            "cases": rows,
            "aggregate": aggregate,
            "error": error,
            "k": 6,
            "baseline_id": previous.id if previous else None,
            "delta": {
                key: value - previous.results.get("aggregate", {}).get(key, value)
                for key, value in aggregate.items()
            }
            if previous
            else {},
            "methodology": {
                "retrieval": "Unique documents; Precision@6 divides by 6 even with fewer results.",
                "faithfulness": "Binary grounding-check pass rate; LLM judged, or verbatim in extractive mode. Not a calibrated semantic score.",
                "answer_relevance": "Token-set F1 against reference answer (lexical proxy).",
                "context_relevance": "Fraction of retrieved chunks from expected documents (label-based proxy).",
                "citation_correctness": "Exact expected document and section match fraction.",
            },
        }
        await db.commit()
        return {
            "id": evaluation.id,
            "status": status,
            "created_at": evaluation.created_at,
            "results": evaluation.results,
        }
