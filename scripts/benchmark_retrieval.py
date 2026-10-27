"""Compare production retrieval components on a frozen labeled corpus, read-only."""

import argparse
import asyncio
import hashlib
import json
import random
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.database.session import Session, engine, require_runtime_role
from app.evaluation.retrieval_benchmark import (
    MODES,
    load_benchmark,
    paired_deltas,
    score_ranking,
    summarize,
)
from app.models.entities import Document, User
from app.reranking.providers import reranker
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.postgres import DenseRetriever, LexicalRetriever, authorized_chunks
from app.security.guardrails import screen_candidates
from app.security.scope import Scope
from sqlalchemy import select, text


async def readonly(scope=None):
    db = Session(scope=scope)
    await db.execute(text("SET TRANSACTION READ ONLY"))
    return db


def public_ranking(items):
    return [{"document": c.document, "section": c.section} for c in items[:6]]


async def run(args):
    dataset, digest, corpus_hashes = load_benchmark(args.dataset, args.corpus)
    cfg = get_settings()
    await require_runtime_role()
    db = await readonly()
    try:
        # Same RLS login lookup as the API; no owner role or unscoped document query.
        await db.execute(
            text("SELECT set_config('app.login_email', :email, true)"),
            {"email": cfg.seed_admin_email},
        )
        user = await db.scalar(select(User).where(User.email == cfg.seed_admin_email))
        if user is None:
            raise ValueError("Configured benchmark user does not exist.")
        scope = Scope(user.tenant_id, user.id, user.role)
    finally:
        await db.close()
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
        actual = {d.name: d.content_hash for d in docs}
        if len(docs) != len(corpus_hashes) or actual != corpus_hashes:
            raise ValueError(
                "Accessible indexed corpus differs from the frozen synthetic source files."
            )
        chunks = (await db.scalars(authorized_chunks(scope))).all()
        labels = {(c.source, c.section) for c in chunks}
        for case in dataset["cases"]:
            if any(
                (s["document"], s["section"]) not in labels
                for s in case["expected_sections"]
            ):
                raise ValueError(f"Unindexed relevance label in {case['id']}")
        snapshot = sorted((c.source, c.section, c.text) for c in chunks)
        snapshot_digest = hashlib.sha256(
            json.dumps(snapshot, ensure_ascii=False).encode()
        ).hexdigest()
    finally:
        await db.close()
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_sha256": digest,
        "dataset_hash_method": "UTF-8 text with CRLF normalized to LF",
        "dataset_original_bytes_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "dataset": dataset,
        "corpus_sha256": corpus_hashes,
        "chunk_snapshot_sha256": snapshot_digest,
        "chunk_count": len(snapshot),
        "repeats": args.repeats,
        "k": 6,
        "candidate_k": 20,
        "configuration": {
            key: getattr(cfg, key)
            for key in (
                "embedding_model",
                "embedding_provider",
                "reranker_model",
                "reranker_provider",
            )
        },
        "methodology": {
            "scope": "New author-labeled synthetic diagnostic questions, frozen before measuring; no parameter tuning.",
            "limits": "Same eight known documents; exact section labels, not independent human judgments. No answer generation or answer-quality claim.",
            "pairing": "Each mode shares the same dense and lexical candidates for each question/repeat. No retries or silent fallback.",
            "latency": "Component-derived, sequential production ordering: dense; dense+lexical+fusion; plus reranking. Excludes auth, routing, LLM, and network-to-API. Not independent end-to-end timings.",
            "ranking": "Actual top six chunks; duplicate section labels receive no extra relevance credit. All specified sections are required labels, not exhaustive judgments of all useful evidence.",
            "intervals": "95% paired percentile bootstrap, 2000 resamples of question clusters; repeats averaged per question. Exploratory, not multiple-comparison adjusted.",
        },
        "rows": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        result["summary"] = summarize(result["rows"])
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    rng = random.Random(20261027)
    for repeat in range(args.repeats):
        cases = list(dataset["cases"])
        rng.shuffle(cases)
        for number, case in enumerate(cases, 1):
            db = await readonly(scope)
            records = []
            stage = "dense"
            try:
                start = time.perf_counter()
                dense = await DenseRetriever(db).retrieve(case["question"], scope, k=20)
                dense_ms = (time.perf_counter() - start) * 1000
                dense_safe, _ = screen_candidates(dense)
                ranking = public_ranking(dense_safe)
                records.append(
                    {
                        "mode": "dense",
                        "status": "COMPLETED",
                        "ranking": ranking,
                        "metrics": score_ranking(ranking, case["expected_sections"]),
                        "latency_ms": dense_ms,
                    }
                )
                stage = "hybrid"
                start = time.perf_counter()
                lexical = await LexicalRetriever(db).retrieve(
                    case["question"], scope, k=20
                )
                fused, _ = screen_candidates(reciprocal_rank_fusion(dense, lexical))
                hybrid_ms = dense_ms + (time.perf_counter() - start) * 1000
                ranking = public_ranking(fused)
                records.append(
                    {
                        "mode": "hybrid",
                        "status": "COMPLETED",
                        "ranking": ranking,
                        "metrics": score_ranking(ranking, case["expected_sections"]),
                        "latency_ms": hybrid_ms,
                    }
                )
                stage = "hybrid_reranked"
                start = time.perf_counter()
                ranked = await reranker().rerank(
                    case["question"], [replace(c) for c in fused]
                )
                reranked_ms = hybrid_ms + (time.perf_counter() - start) * 1000
                ranking = public_ranking(ranked)
                records.append(
                    {
                        "mode": stage,
                        "status": "COMPLETED",
                        "ranking": ranking,
                        "metrics": score_ranking(ranking, case["expected_sections"]),
                        "latency_ms": reranked_ms,
                    }
                )
            except Exception as exc:  # noqa: BLE001 -- record failed modes; never silently substitute a ranking
                completed = {r["mode"] for r in records}
                for mode in MODES:
                    if mode not in completed:
                        records.append(
                            {
                                "mode": mode,
                                "status": "FAILED",
                                "error_type": type(exc).__name__,
                                "failed_stage": stage,
                            }
                        )
                # Preserve full traceback privately without printing response bodies or credentials.
                import traceback

                with args.output.with_suffix(".errors.log").open(
                    "a", encoding="utf-8"
                ) as log:
                    log.write(f"{case['id']} repeat={repeat} stage={stage}\n")
                    traceback.print_exc(file=log)
            finally:
                await db.close()
            for record in records:
                record.update(case_id=case["id"], repeat=repeat + 1)
            result["rows"].extend(records)
            save()
            print(
                json.dumps(
                    {
                        "repeat": repeat + 1,
                        "case": number,
                        "total": len(cases),
                        "id": case["id"],
                        "failed": [
                            r["mode"] for r in records if r["status"] != "COMPLETED"
                        ],
                    }
                ),
                flush=True,
            )
    db = await readonly(scope)
    try:
        final_chunks = (await db.scalars(authorized_chunks(scope))).all()
        final_snapshot = sorted((c.source, c.section, c.text) for c in final_chunks)
        final_digest = hashlib.sha256(
            json.dumps(final_snapshot, ensure_ascii=False).encode()
        ).hexdigest()
        if final_digest != snapshot_digest:
            raise ValueError(
                "Indexed corpus changed during benchmarking; results are not comparable."
            )
        result["corpus_unchanged_at_end"] = True
    finally:
        await db.close()
    result["paired_comparisons"] = [
        paired_deltas(result["rows"], a, b)
        for a, b in (
            ("dense", "hybrid"),
            ("hybrid", "hybrid_reranked"),
            ("dense", "hybrid_reranked"),
        )
    ]
    result["completed_at"] = datetime.now(timezone.utc).isoformat()
    save()
    print(json.dumps(result["summary"], indent=2))
    await engine.dispose()
    return 1 if any(r["status"] != "COMPLETED" for r in result["rows"]) else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "data/demo/retrieval-holdout.json"
    )
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/demo")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".local/deployment/retrieval-ablation.json",
    )
    parser.add_argument("--repeats", type=int, choices=range(1, 6), default=3)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
