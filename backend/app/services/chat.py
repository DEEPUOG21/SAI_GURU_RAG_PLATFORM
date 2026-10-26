import asyncio
import json
import logging
import time

from sqlalchemy import select

from app.agents.workflow import execute
from app.core.config import get_settings
from app.database.session import Session
from app.models.entities import Chunk, Message, Query, RetrievalResult
from app.observability.trace import Trace
from app.services.access import sources_visible
from app.services.conversation import ConversationHistory, bounded_history, history_sources


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def persist_candidates(db, query_id, candidates):
    existing = set(
        (
            await db.scalars(
                select(Chunk.id)
                .where(Chunk.id.in_([c.chunk_id for c in candidates]))
                .with_for_update(read=True)
            )
        ).all()
    )
    for candidate in candidates:
        db.add(
            RetrievalResult(
                query_id=query_id,
                chunk_id=candidate.chunk_id if candidate.chunk_id in existing else None,
                metadata_snapshot=candidate.serialize(),
                dense_score=candidate.dense_score,
                lexical_score=candidate.lexical_score,
                rrf_score=candidate.rrf_score,
                reranker_score=candidate.reranker_score,
            )
        )


async def chat_stream(query_id, conversation_id, question, scope, history, request):
    queue = asyncio.Queue(maxsize=64)
    trace, started = Trace(), time.perf_counter()

    async def emit(event, data):
        await queue.put((event, data))

    async def run():
        try:
            async with Session(scope=scope) as db:
                async with asyncio.timeout(get_settings().query_timeout_seconds):
                    result = await execute(db, scope, question, history, emit, trace)
                query = await db.get(Query, query_id)
                for key in (
                    "answer",
                    "route",
                    "rewritten_query",
                    "grounding",
                    "trace",
                    "latency_ms",
                    "token_usage",
                    "estimated_cost",
                ):
                    setattr(query, key, result[key])
                query.status = "COMPLETED"
                await persist_candidates(db, query_id, result["candidates"])
                message = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=result["answer"],
                    citations=result["citations"],
                    query_id=query_id,
                )
                db.add(message)
                await db.commit()
                await emit(
                    "final",
                    {
                        "answer": result["answer"],
                        "citations": result["citations"],
                        "query_id": query_id,
                        "message_id": message.id,
                        "grounding": result["grounding"],
                        "latency_ms": result["latency_ms"],
                        "guardrails": result.get("guardrails", []),
                    },
                )
        except (Exception, asyncio.CancelledError) as exc:
            cancelled = isinstance(exc, asyncio.CancelledError)
            error_type = type(exc).__name__
            logging.error("query_failed query_id=%s error_type=%s", query_id, error_type)

            async def persist_failure():
                async with Session(scope=scope) as db:
                    query = await db.get(Query, query_id)
                    if query and query.status != "COMPLETED":
                        query.status, query.error = ("CANCELLED" if cancelled else "FAILED"), error_type
                        query.trace, query.latency_ms = trace.steps, (time.perf_counter() - started) * 1000
                        for step in trace.steps:
                            if step["node"] == "query_classifier":
                                query.route = step["output"]
                            if step["node"] == "query_rewriter":
                                query.rewritten_query = step["output"]
                        await persist_candidates(db, query_id, trace.candidates)
                        await db.commit()

            try:
                await asyncio.shield(persist_failure())
            except Exception as persistence_error:
                logging.error(
                    "query_failure_persistence_failed query_id=%s error_type=%s",
                    query_id,
                    type(persistence_error).__name__,
                )
            if not cancelled:
                await emit(
                    "error",
                    {
                        "message": "Query failed. Check provider configuration and the retrieval trace.",
                        "query_id": query_id,
                    },
                )
        finally:
            if not asyncio.current_task().cancelling():
                await queue.put(("done", {}))

    task = asyncio.create_task(run())
    try:
        yield sse("meta", {"query_id": query_id, "conversation_id": conversation_id})
        while True:
            if await request.is_disconnected():
                logging.info("chat_client_disconnected query_id=%s", query_id)
                break
            try:
                event, data = await asyncio.wait_for(queue.get(), timeout=10)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield sse(event, data)
            if event == "done":
                break
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def conversation_history(db, id, scope):
    rows = (
        await db.execute(
            select(Message, Query.trace)
            .outerjoin(Query, Message.query_id == Query.id)
            .where(Message.conversation_id == id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(20)
        )
    ).all()
    history, dependencies = [], {}
    for row, trace in reversed(rows):
        sources = (row.citations or []) + history_sources(trace)
        if row.role == "assistant" and not await sources_visible(db, scope, sources):
            # Do not give the model old private content after deletion, version or role changes.
            history.append(
                {
                    "role": "assistant",
                    "content": "Earlier source content is no longer available. Retrieve current authorized evidence.",
                }
            )
        elif row.role in {"user", "assistant"}:
            history.append({"role": row.role, "content": row.content})
            if row.role == "assistant":
                for source in sources:
                    metadata = {key: source.get(key) for key in ("document_id", "version", "kind")}
                    dependencies[json.dumps(metadata, sort_keys=True)] = metadata
    return ConversationHistory(bounded_history(history), list(dependencies.values()))
