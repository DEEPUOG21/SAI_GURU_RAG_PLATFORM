"""Durable PostgreSQL queue: deploy this process or use the authenticated process endpoint."""

import asyncio
import logging
import os

from sqlalchemy import select, text

from app.database.session import Session, engine, require_runtime_role
from app.ingestion.service import process
from app.models.entities import Document
from app.security.scope import Scope


async def process_one(document_id: str | None = None, scope=None):
    if document_id is not None:
        return await _process_one(document_id, scope)
    # Background workers share the API's global heavy-work slots.
    async with engine.connect() as admission:
        slot = None
        for candidate in range(2):
            if await admission.scalar(text("SELECT pg_try_advisory_lock(19471, :slot)"), {"slot": candidate}):
                slot = candidate
                break
        if slot is None:
            return False
        try:
            return await _process_one(document_id, scope)
        finally:
            await admission.execute(text("SELECT pg_advisory_unlock(19471, :slot)"), {"slot": slot})


async def _process_one(document_id: str | None = None, scope=None):
    async with engine.connect() as lock_connection:
        async with Session(scope=scope) as db:
            statement = select(Document).where(
                Document.status.in_(["UPLOADED", "PARSING", "CHUNKING", "EMBEDDING", "INDEXING"])
            )
            if document_id:
                statement = statement.where(Document.id == document_id)
            docs = (await db.scalars(statement.order_by(Document.created_at).limit(20))).all()
            for doc in docs:
                key = doc.id
                locked = await lock_connection.scalar(
                    text("SELECT pg_try_advisory_lock(hashtext(:key))"), {"key": key}
                )
                if not locked:
                    continue
                try:
                    await db.refresh(doc)
                    if doc.status == "COMPLETED":
                        continue
                    async with asyncio.timeout(600):
                        await process(db, doc)
                except Exception:
                    logging.error("document_processing_failed document_id=%s", key)
                    await db.rollback()
                    await db.refresh(doc)
                    doc.status, doc.error = (
                        "FAILED",
                        "Processing failed or timed out. Retry after checking provider configuration.",
                    )
                    await db.commit()
                finally:
                    await lock_connection.execute(
                        text("SELECT pg_advisory_unlock(hashtext(:key))"), {"key": key}
                    )
                return True
    return False


async def main():
    await require_runtime_role()
    tenant_id = os.environ.get("WORKER_TENANT_ID")
    if not tenant_id:
        raise RuntimeError(
            "Set WORKER_TENANT_ID for a tenant-scoped worker, or use authenticated request-driven processing."
        )
    scope = Scope(tenant_id, "worker", "ADMIN")
    while True:
        try:
            if not await process_one(scope=scope):
                await asyncio.sleep(3)
        except Exception:
            logging.error("worker_poll_failed")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
