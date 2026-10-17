from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text

from app.api.documents import serialize
from app.core.config import get_settings
from app.database.session import get_db
from app.models.entities import Document, Query, RetrievalResult
from app.schemas.responses import DashboardResponse, DebugResponse
from app.security.auth import current_scope
from app.services.access import sources_visible
from app.services.conversation import history_sources

router = APIRouter(prefix="/api/v1", tags=["Observability"])


@router.get("/ready")
async def ready(db=Depends(get_db)):
    try:
        version = await db.scalar(text("SELECT version_num FROM alembic_version"))
        vector = await db.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        if version != "0004" or not vector:
            raise ValueError("Migrations incomplete")
    except Exception as exc:
        raise HTTPException(503, "Database unavailable or migrations incomplete.") from exc
    return {
        "status": "ready",
        "database": "connected",
        "pgvector": vector,
        "generation_mode": get_settings().generation_mode,
        "providers": "checked on use; readiness does not guarantee model availability",
    }


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(scope=Depends(current_scope), db=Depends(get_db)):
    doc_filter = (Document.tenant_id == scope.tenant_id, Document.min_role <= scope.level)
    query_filter = (Query.tenant_id == scope.tenant_id, Query.user_id == scope.user_id)
    total = await db.scalar(select(func.count()).select_from(Query).where(*query_filter))
    successful = await db.scalar(
        select(func.count()).select_from(Query).where(*query_filter, Query.status == "COMPLETED")
    )
    latency = await db.scalar(
        select(func.avg(Query.latency_ms)).where(*query_filter, Query.status == "COMPLETED")
    )
    documents = (
        await db.scalars(select(Document).where(*doc_filter).order_by(Document.updated_at.desc()).limit(5))
    ).all()
    recent = (
        await db.scalars(select(Query).where(*query_filter).order_by(Query.created_at.desc()).limit(6))
    ).all()
    return {
        "documents_indexed": await db.scalar(
            select(func.count()).select_from(Document).where(*doc_filter, Document.status == "COMPLETED")
        ),
        "total_queries": total,
        "successful_queries": successful,
        "average_latency_ms": latency,
        "recent_documents": [serialize(doc) for doc in documents],
        "recent_queries": [
            {
                "id": q.id,
                "question": q.question,
                "route": q.route,
                "status": q.status,
                "latency_ms": q.latency_ms,
                "created_at": q.created_at,
            }
            for q in recent
        ],
        "scope": "Documents you can access; query metrics for your account.",
        "generation_mode": get_settings().generation_mode,
    }


@router.get("/retrieval/debug/{query_id}", response_model=DebugResponse)
async def debug(query_id: str, scope=Depends(current_scope), db=Depends(get_db)):
    query = await db.scalar(
        select(Query).where(
            Query.id == query_id, Query.tenant_id == scope.tenant_id, Query.user_id == scope.user_id
        )
    )
    if not query:
        raise HTTPException(404, "Query not found.")
    rows = (await db.scalars(select(RetrievalResult).where(RetrievalResult.query_id == query.id))).all()
    sources = [row.metadata_snapshot for row in rows]
    if (query.route in {"SQL", "HYBRID"} and scope.level < 1) or not await sources_visible(
        db, scope, sources + history_sources(query.trace)
    ):
        raise HTTPException(403, "Source access changed. Run a new query to inspect current evidence.")
    return {
        key: getattr(query, key)
        for key in (
            "id",
            "question",
            "rewritten_query",
            "route",
            "status",
            "grounding",
            "answer",
            "latency_ms",
            "token_usage",
            "estimated_cost",
            "trace",
            "error",
            "request_id",
        )
    } | {"candidates": sources}
