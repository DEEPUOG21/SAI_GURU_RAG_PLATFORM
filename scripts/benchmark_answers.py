"""Run a frozen 60-case answer/abstention/conversation comparison without database writes."""

import argparse
import asyncio
import hashlib
import json
import random
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agents.workflow import execute
from app.core.config import get_settings
from app.database.session import engine, require_runtime_role
from app.evaluation.answer_benchmark import (
    MODES,
    answer_summary,
    attach_reviews,
    load_answer_benchmark,
    paired_answer_comparisons,
    retrieval_mode,
)
from app.models.entities import Document, User
from app.observability.trace import Trace
from app.retrieval.postgres import authorized_chunks
from app.security.scope import Scope
from app.services.conversation import ConversationHistory
from benchmark_retrieval import readonly
from sqlalchemy import select, text


async def main(args):
    dataset, digest = load_answer_benchmark(args.dataset, ROOT / "data/demo")
    if args.reviews:
        record = json.loads(args.output.read_text(encoding="utf-8"))
        expected = {
            (c["id"], mode, turn)
            for c in dataset["cases"]
            for mode in MODES
            for turn in (["setup", "target"] if "setup_question" in c else ["target"])
        }
        actual = {(r["case_id"], r["mode"], r["turn"]) for r in record["rows"]}
        if (
            record["dataset_sha256"] != digest
            or record["dataset"] != dataset
            or not record.get("completed_at")
            or not record.get("corpus_unchanged_at_end")
            or actual != expected
            or len(record["rows"]) != len(expected)
            or any(r["status"] != "COMPLETED" for r in record["rows"])
        ):
            raise ValueError(
                "Review import requires a complete matching run and unchanged corpus."
            )
        attach_reviews(record, json.loads(args.reviews.read_text(encoding="utf-8")))
        record["summary"] = answer_summary(record)
        record["paired_comparisons"] = paired_answer_comparisons(record)
        record.setdefault(
            "review_provenance",
            {
                "method": "Externally supplied source-based annotations; see per-answer reasons."
            },
        )
        args.output.write_bytes((json.dumps(record, indent=2) + "\n").encode("utf-8"))
        if args.public_output:
            public = json.loads(json.dumps(record))
            for row in public["rows"]:
                row.pop("citation_sources", None)
                row["trace"] = [
                    {k: v for k, v in step.items() if k != "output"}
                    for step in row["trace"]
                ]
            args.public_output.parent.mkdir(parents=True, exist_ok=True)
            args.public_output.write_bytes(
                (json.dumps(public, indent=2) + "\n").encode("utf-8")
            )
        print(json.dumps(record["summary"], indent=2))
        return
    cfg = get_settings()
    if cfg.generation_mode != "llm":
        raise ValueError("An actual LLM is required for this answer study.")
    await require_runtime_role()
    db = await readonly()
    try:
        await db.execute(
            text("SELECT set_config('app.login_email', :email, true)"),
            {"email": cfg.seed_admin_email},
        )
        user = await db.scalar(select(User).where(User.email == cfg.seed_admin_email))
        scope = Scope(user.tenant_id, user.id, user.role)
    finally:
        await db.close()

    async def snapshot():
        db = await readonly(scope)
        try:
            docs = (
                await db.scalars(
                    select(Document).where(
                        Document.tenant_id == scope.tenant_id,
                        Document.min_role <= scope.level,
                        Document.status == "COMPLETED",
                    )
                )
            ).all()
            expected = {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (ROOT / "data/demo").glob("*.md")
            }
            if len(docs) != 8 or {d.name: d.content_hash for d in docs} != expected:
                raise ValueError(
                    "Indexed corpus differs from the frozen synthetic source files."
                )
            chunks = (await db.scalars(authorized_chunks(scope))).all()
            return hashlib.sha256(
                json.dumps(
                    sorted((c.source, c.section, c.text) for c in chunks),
                    ensure_ascii=False,
                ).encode()
            ).hexdigest()
        finally:
            await db.close()

    corpus_hash = await snapshot()
    configuration = {
        k: getattr(cfg, k)
        for k in (
            "llm_model",
            "llm_provider",
            "embedding_model",
            "reranker_model",
            "generation_mode",
            "guardrails_enabled",
            "grounding_action",
            "general_fallback_enabled",
        )
    }
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset,
        "dataset_sha256": digest,
        "corpus_snapshot_sha256": corpus_hash,
        "configuration": configuration,
        "methodology": {
            "baseline": "Dense-only top six via process-local adapter. Lexical returns no candidates and reranking preserves dense order; all guards, generation, grounding, resolver and context budgets stay fixed.",
            "current": "Unmodified hybrid RRF plus reranking workflow.",
            "order": "Seeded shuffled cases and randomized mode order; one response per target/mode; actual generated setup answers feed follow-up history. Not a perfectly balanced crossover design.",
            "latency": "Workflow duration including resolution, retrieval, authorization recheck, generation and verification; excludes HTTP auth, SSE transport, persistence and session setup. No sustained-load claim.",
            "scoring": dataset["rubric"],
            "limits": "Same known synthetic corpus; author-generated questions; one observation per target/mode. Coding-agent semantic review is not independent human evaluation. Production guards remain enabled in both modes.",
        },
        "rows": [],
    }
    if args.resume:
        old = json.loads(args.output.read_text(encoding="utf-8"))
        if any(row["status"] != "COMPLETED" for row in old["rows"]):
            raise ValueError(
                "Failed trials are retained. Use a distinct output file for a new run after resolving the external failure; do not replace failed measurements."
            )
        if (
            old["dataset_sha256"] != digest
            or old["corpus_snapshot_sha256"] != corpus_hash
            or old["configuration"] != configuration
        ):
            raise ValueError(
                "Cannot resume after dataset, corpus or configuration changes."
            )
        record = old
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        record["summary"] = answer_summary(record)
        args.output.write_bytes((json.dumps(record, indent=2) + "\n").encode("utf-8"))

    save()
    completed = {(r["case_id"], r["mode"], r["turn"]): r for r in record["rows"]}
    rng = random.Random(20261027)
    cases = list(dataset["cases"])
    rng.shuffle(cases)
    for number, case in enumerate(cases, 1):
        modes = list(MODES)
        rng.shuffle(modes)
        for mode in modes:
            history, sources = [], []
            turns = (
                [("setup", case["setup_question"]), ("target", case["question"])]
                if "setup_question" in case
                else [("target", case["question"])]
            )
            for turn, question in turns:
                key = (case["id"], mode, turn)
                trace = Trace()
                citations = []
                if key in completed:
                    row = completed[key]
                    if turn == "setup":
                        # Resume re-resolves authorized source IDs from current read-only chunks below.
                        citations = row.get("citation_sources", [])
                else:
                    db = await readonly(scope)
                    row = {
                        "case_id": case["id"],
                        "mode": mode,
                        "turn": turn,
                        "review_id": hashlib.sha256(
                            (digest + ":" + ":".join(key)).encode()
                        ).hexdigest()[:16],
                    }
                    try:

                        async def discard(event, data):
                            if event == "draft":
                                raise RuntimeError(
                                    "Unchecked draft output must not be emitted."
                                )

                        with (
                            retrieval_mode(mode),
                            __import__("langsmith").tracing_context(enabled=False),
                        ):
                            async with asyncio.timeout(300):
                                result = await execute(
                                    db,
                                    scope,
                                    question,
                                    ConversationHistory(history, sources),
                                    discard,
                                    trace,
                                )
                        citations = result["citations"]
                        row.update(
                            status="COMPLETED",
                            answer=result["answer"],
                            grounding=result["grounding"],
                            route=result["route"],
                            rewritten_query=result["rewritten_query"],
                            latency_ms=result["latency_ms"],
                            token_usage=result["token_usage"],
                            citations=[
                                {
                                    k: c.get(k)
                                    for k in ("label", "document", "section", "text")
                                }
                                for c in citations
                            ],
                            guardrails=result["guardrails"],
                            trace=[
                                {k: v for k, v in step.items() if k != "output"}
                                for step in trace.steps
                            ],
                        )
                        # Private checkpoint only; strip these scoped IDs when publishing evidence.
                        row["citation_sources"] = [
                            {k: c.get(k) for k in ("document_id", "version", "kind")}
                            for c in citations
                        ]
                    except Exception as exc:  # noqa: BLE001 -- retain failed trials rather than retry for better scores
                        row.update(
                            status="FAILED",
                            error_type=type(exc).__name__,
                            trace=trace.steps,
                        )
                        if hasattr(exc, "response"):
                            row["provider_status_code"] = exc.response.status_code
                        with args.output.with_suffix(".errors.log").open(
                            "a", encoding="utf-8"
                        ) as log:
                            log.write(f"{key}\n")
                            traceback.print_exc(file=log)
                    finally:
                        await db.close()
                    record["rows"].append(row)
                    completed[key] = row
                    save()
                    print(
                        json.dumps(
                            {
                                "case": number,
                                "total": 60,
                                "id": case["id"],
                                "mode": mode,
                                "turn": turn,
                                "status": row["status"],
                            }
                        ),
                        flush=True,
                    )
                if row["status"] != "COMPLETED":
                    raise RuntimeError(
                        "A trial failed and is retained. Inspect the private log; use a distinct output for a new run. No automatic retry or paid upgrade."
                    )
                if turn == "setup":
                    history = [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": row["answer"]},
                    ]
                    sources = citations
    if await snapshot() != corpus_hash:
        raise ValueError("Corpus changed during the comparison.")
    record["corpus_unchanged_at_end"] = True
    record["completed_at"] = datetime.now(timezone.utc).isoformat()
    save()
    await engine.dispose()
    print(json.dumps(record["summary"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "data/demo/answer-holdout.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".local/deployment/answer-comparison.json"
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--reviews",
        type=Path,
        help="Attach complete source-based review labels to an existing completed run; no inference or database access",
    )
    parser.add_argument(
        "--public-output",
        type=Path,
        help="With --reviews, write evidence with scoped resource IDs and trace outputs removed",
    )
    args = parser.parse_args()
    if args.public_output and not args.reviews:
        parser.error("--public-output requires --reviews")
    asyncio.run(main(args))
