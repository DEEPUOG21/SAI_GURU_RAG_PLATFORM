from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import Text, cast, delete, func, or_, select, text

from app.core.config import get_settings
from app.database.session import get_db
from app.ingestion.service import upload
from app.ingestion.worker import process_one
from app.models.entities import Chunk, Document, Evaluation, Message, RetrievalResult
from app.models.entities import Query as SavedQuery
from app.schemas.responses import DocumentDetail, DocumentResponse
from app.security.auth import current_scope, rate_limit, require_role

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])


def serialize(doc):
    return {
        key: getattr(doc, key)
        for key in (
            "id",
            "name",
            "version",
            "status",
            "size",
            "min_role",
            "error",
            "created_at",
            "updated_at",
        )
    }


async def authorized_document(db, scope, id):
    doc = await db.scalar(
        select(Document).where(
            Document.id == id, Document.tenant_id == scope.tenant_id, Document.min_role <= scope.level
        )
    )
    if not doc:
        raise HTTPException(404, "Document not found.")
    return doc


@router.get("", response_model=list[DocumentResponse])
async def listing(
    search: str = Query("", max_length=200),
    status: str = Query("", max_length=20),
    scope=Depends(current_scope),
    db=Depends(get_db),
):
    statement = select(Document).where(
        Document.tenant_id == scope.tenant_id, Document.min_role <= scope.level
    )
    if search:
        statement = statement.where(
            Document.name.ilike("%" + search.replace("%", "\\%").replace("_", "\\_") + "%")
        )
    if status:
        statement = statement.where(Document.status == status)
    return [
        serialize(doc)
        for doc in (await db.scalars(statement.order_by(Document.updated_at.desc()).limit(200))).all()
    ]


@router.post("", status_code=201, response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...), min_role: int = Form(0), scope=Depends(current_scope), db=Depends(get_db)
):
    require_role(scope, 1)
    if min_role < 0 or min_role > scope.level:
        raise HTTPException(403, "Cannot assign a document above your own access level.")
    await rate_limit(db, "upload:" + scope.user_id, 10)
    content = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    existing = await db.scalar(
        select(Document).where(Document.tenant_id == scope.tenant_id, Document.name == file.filename)
    )
    if existing and existing.min_role > scope.level:
        raise HTTPException(403, "A restricted document already uses this name.")
    try:
        return serialize(
            await upload(db, scope.tenant_id, file.filename or "", content, min_role, scope.level)
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/{id}", response_model=DocumentDetail)
async def detail(id: str, scope=Depends(current_scope), db=Depends(get_db)):
    doc = await authorized_document(db, scope, id)
    chunks = (
        await db.scalars(
            select(Chunk)
            .where(Chunk.document_id == doc.id, Chunk.tenant_id == scope.tenant_id)
            .order_by(Chunk.created_at, Chunk.id)
            .limit(50)
        )
    ).all()
    return {
        **serialize(doc),
        "chunks": [{"id": c.id, "text": c.text, "page": c.page, "section": c.section} for c in chunks],
        "chunk_count": await db.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.document_id == doc.id)
        ),
    }


@router.post("/{id}/process", response_model=DocumentResponse)
async def process_document(id: str, scope=Depends(current_scope), db=Depends(get_db)):
    require_role(scope, 1)
    await rate_limit(db, "process:" + scope.user_id, 10)
    doc = await authorized_document(db, scope, id)
    if doc.status == "FAILED":
        doc.status, doc.error = "UPLOADED", None
        await db.commit()
    # Request-driven processing supports free hosts without paid background workers.
    await process_one(doc.id, scope=scope)
    await db.refresh(doc)
    return serialize(doc)


@router.delete("/{id}", status_code=204)
async def remove(id: str, scope=Depends(current_scope), db=Depends(get_db)):
    require_role(scope, 1)
    doc = await authorized_document(db, scope, id)
    if not await db.scalar(text("SELECT pg_try_advisory_xact_lock(hashtext(:id))"), {"id": doc.id}):
        raise HTTPException(409, "Document is locked by the ingestion worker. Retry after processing.")
    if doc.status not in {"COMPLETED", "FAILED", "UPLOADED"}:
        raise HTTPException(409, "Wait for processing to finish before deleting.")
    # Remove derived content, including conversation descendants that depend on this source.
    affected = select(SavedQuery.id).where(
        SavedQuery.tenant_id == scope.tenant_id,
        or_(
            cast(SavedQuery.trace, Text).contains(doc.id),
            SavedQuery.id.in_(
                select(RetrievalResult.query_id).where(
                    cast(RetrievalResult.metadata_snapshot, Text).contains(doc.id)
                )
            ),
        ),
    )
    ids = list((await db.scalars(affected)).all())
    if ids:
        await db.execute(delete(Message).where(Message.query_id.in_(ids)))
        await db.execute(
            delete(SavedQuery).where(SavedQuery.id.in_(ids), SavedQuery.tenant_id == scope.tenant_id)
        )
    await db.execute(
        delete(Evaluation).where(
            Evaluation.tenant_id == scope.tenant_id, cast(Evaluation.results, Text).contains(doc.id)
        )
    )
    await db.execute(delete(Document).where(Document.id == doc.id, Document.tenant_id == scope.tenant_id))
    await db.commit()
