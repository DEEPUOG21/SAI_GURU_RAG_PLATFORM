import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.database.retention import run
from app.database.session import Session, engine
from app.models.entities import Conversation, Message, Query, Tenant, User

pytestmark = pytest.mark.skipif(os.getenv("SAI_INTEGRATION") != "1", reason="Requires test PostgreSQL")


async def test_retention_preview_and_apply_only_touch_expired_target_tenant():
    async with Session() as db:
        tenants = [Tenant(name="Retention A"), Tenant(name="Retention B")]
        db.add_all(tenants)
        await db.flush()
        users = [
            User(tenant_id=t.id, email=t.id + "@retention.example", password_hash="unused", role="ADMIN")
            for t in tenants
        ]
        db.add_all(users)
        await db.flush()
        queries = []
        for user, days in [(users[0], 40), (users[0], 1), (users[1], 40)]:
            conversation = Conversation(tenant_id=user.tenant_id, user_id=user.id, title="retention")
            db.add(conversation)
            await db.flush()
            query = Query(
                tenant_id=user.tenant_id,
                user_id=user.id,
                conversation_id=conversation.id,
                question="synthetic",
                request_id="retention-test",
                status="COMPLETED",
                created_at=datetime.now(timezone.utc) - timedelta(days=days),
            )
            db.add(query)
            await db.flush()
            db.add(
                Message(conversation_id=conversation.id, query_id=query.id, role="user", content="synthetic")
            )
            queries.append(query.id)
        await db.commit()
        try:
            await run(tenants[0].id, 30, False)
            assert len((await db.scalars(select(Query.id).where(Query.id.in_(queries)))).all()) == 3
            await db.commit()
            await run(tenants[0].id, 30, True)
            remaining = set((await db.scalars(select(Query.id).where(Query.id.in_(queries)))).all())
            assert remaining == set(queries[1:])
            assert not (await db.scalars(select(Message.id).where(Message.query_id == queries[0]))).all()
        finally:
            for tenant in tenants:
                await db.execute(delete(Query).where(Query.tenant_id == tenant.id))
                await db.execute(delete(Conversation).where(Conversation.tenant_id == tenant.id))
                await db.execute(delete(User).where(User.tenant_id == tenant.id))
                await db.delete(tenant)
            await db.commit()
    await engine.dispose()
