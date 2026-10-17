"""Explicit tenant-scoped retention maintenance. Preview by default; --apply deletes expired history."""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.database.session import Session, engine
from app.models.entities import Conversation, Evaluation, Message, Query
from app.security.scope import Scope


async def run(tenant_id, days=30, apply=False):
    if not 1 <= days <= 3650:
        raise ValueError("Retention days must be between 1 and 3650")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with Session(scope=Scope(tenant_id, "maintenance", "ADMIN")) as db:
        expired = select(Query.id).where(
            Query.tenant_id == tenant_id, Query.created_at < cutoff, Query.status != "RUNNING"
        )
        count = await db.scalar(select(func.count()).select_from(expired.subquery()))
        if apply:
            await db.execute(delete(Message).where(Message.query_id.in_(expired)))
            await db.execute(delete(Query).where(Query.id.in_(expired)))
            await db.execute(
                delete(Evaluation).where(
                    Evaluation.tenant_id == tenant_id,
                    Evaluation.created_at < cutoff,
                    Evaluation.status != "RUNNING",
                )
            )
            await db.execute(
                delete(Conversation).where(
                    Conversation.tenant_id == tenant_id,
                    Conversation.created_at < cutoff,
                    ~Conversation.id.in_(select(Message.conversation_id)),
                )
            )
            await db.commit()
        print(f"{'Deleted' if apply else 'Would delete'} {count} expired queries and their derived content.")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.tenant, args.days, args.apply))
