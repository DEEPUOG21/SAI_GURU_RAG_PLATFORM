from sqlalchemy import select

from app.models.entities import Document


async def sources_visible(db, scope, citations):
    """Recheck source access on history/debug reads after document deletion, replacement or role changes."""
    for source in citations:
        if source.get("kind") == "sql":
            if scope.level < 1:
                return False
            continue
        doc_id = source.get("document_id")
        if not doc_id:
            return False
        found = await db.scalar(
            select(Document.id).where(
                Document.id == doc_id,
                Document.tenant_id == scope.tenant_id,
                Document.min_role <= scope.level,
                Document.version == source.get("version"),
                Document.status == "COMPLETED",
            )
        )
        if not found:
            return False
    return True
