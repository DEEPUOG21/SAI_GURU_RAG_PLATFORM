import hashlib
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.ingestion.parsing import chunk_sections, validate_file
from app.ingestion.sandbox import parse_isolated
from app.models.entities import Chunk, Document, DocumentVersion
from app.services.providers import embeddings


async def upload(
    db: AsyncSession, tenant_id: str, name: str, content: bytes, min_role: int = 0, actor_level: int = 2
):
    validate_file(name, content, get_settings().max_upload_mb)
    # Serialize updates to the same logical document, including concurrent first uploads.
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": tenant_id + name})
    digest = hashlib.sha256(content).hexdigest()
    doc = await db.scalar(
        select(Document).where(Document.tenant_id == tenant_id, Document.name == name).with_for_update()
    )
    if doc and doc.min_role > actor_level:
        raise PermissionError("Document access changed. You cannot replace this restricted document.")
    if doc and doc.status not in {"COMPLETED", "FAILED"}:
        raise ValueError("Document is processing. Wait before replacing it.")
    if doc and doc.content_hash == digest and doc.min_role == min_role and doc.status == "COMPLETED":
        return doc
    if doc:
        doc.version += 1
        doc.content_hash, doc.size, doc.status, doc.error = digest, len(content), "UPLOADED", None
        doc.min_role, doc.updated_at = min_role, datetime.now(timezone.utc)
        await db.execute(delete(Chunk).where(Chunk.document_id == doc.id, Chunk.tenant_id == tenant_id))
    else:
        doc = Document(
            tenant_id=tenant_id, name=name, content_hash=digest, size=len(content), min_role=min_role
        )
        db.add(doc)
        await db.flush()
    db.add(
        DocumentVersion(
            tenant_id=tenant_id, document_id=doc.id, version=doc.version, content=content, content_hash=digest
        )
    )
    await db.commit()
    return doc


async def process(db: AsyncSession, doc: Document):
    async def status(value):
        doc.status, doc.updated_at = value, datetime.now(timezone.utc)
        await db.commit()

    try:
        await status("PARSING")
        version = await db.scalar(
            select(DocumentVersion).where(
                DocumentVersion.document_id == doc.id,
                DocumentVersion.tenant_id == doc.tenant_id,
                DocumentVersion.version == doc.version,
            )
        )
        sections = await parse_isolated(doc.name, version.content)
        await status("CHUNKING")
        chunks = chunk_sections(sections)
        await status("EMBEDDING")
        vectors = []
        for offset in range(0, len(chunks), 32):
            vectors.extend(
                await embeddings().embed([f"{s.heading}\n{s.text}" for s in chunks[offset : offset + 32]])
            )
        if len(vectors) != len(chunks) or any(len(v) != 384 for v in vectors):
            raise ValueError("Embedding provider returned invalid dimensions or count.")
        await status("INDEXING")
        await db.execute(delete(Chunk).where(Chunk.document_id == doc.id, Chunk.tenant_id == doc.tenant_id))
        for section, vector in zip(chunks, vectors, strict=True):
            db.add(
                Chunk(
                    tenant_id=doc.tenant_id,
                    document_id=doc.id,
                    version=doc.version,
                    text=section.text,
                    page=section.page,
                    section=section.heading,
                    source=doc.name,
                    embedding=vector,
                    search_vector=func.to_tsvector("english", section.heading + " " + section.text),
                )
            )
        await status("COMPLETED")
    except Exception as exc:
        await db.rollback()
        doc.status, doc.error = "FAILED", f"{type(exc).__name__}: processing failed; inspect worker logs."
        await db.commit()
        raise
