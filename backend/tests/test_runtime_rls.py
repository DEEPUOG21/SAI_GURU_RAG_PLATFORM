"""Real non-owner connection: deliberately omit tenant filters to test database policies."""

import os
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database.session import ScopedSession, Session, engine, get_db
from app.main import app, lifespan
from app.models.entities import Conversation, Document, Evaluation, Message, Query, Tenant, User
from app.security.auth import create_token
from app.security.scope import Scope

pytestmark = pytest.mark.skipif(os.getenv("SAI_INTEGRATION") != "1", reason="Requires prepared PostgreSQL")


async def test_runtime_role_isolation_survives_commit_and_pool_reuse():
    with pytest.raises(RuntimeError, match="non-owner sai_runtime"):
        async with lifespan(app):
            raise AssertionError("API accepted migration-owner credentials")
    runtime_url = (
        os.environ.get("TEST_RUNTIME_DATABASE_URL") or Path(".local-runtime-url").read_text().strip()
    )
    runtime_engine = create_async_engine(runtime_url, pool_size=1, max_overflow=0)
    Runtime = async_sessionmaker(runtime_engine, class_=ScopedSession, expire_on_commit=False)
    suffix = uuid.uuid4().hex
    async with Session() as owner:
        tenants = [Tenant(name="RLS A"), Tenant(name="RLS B")]
        owner.add_all(tenants)
        await owner.flush()
        users = [
            User(tenant_id=t.id, email=f"{i}-{suffix}@rls.example", password_hash="unused", role="ADMIN")
            for i, t in enumerate(tenants)
        ]
        owner.add_all(users)
        owner.add_all(
            [Document(tenant_id=t.id, name="Private.md", content_hash="x", size=1) for t in tenants]
        )
        await owner.commit()
        conversations = [
            Conversation(tenant_id=u.tenant_id, user_id=u.id, title="Delete test") for u in users
        ]
        owner.add_all(conversations)
        await owner.flush()
        queries = [
            Query(
                tenant_id=u.tenant_id,
                user_id=u.id,
                conversation_id=c.id,
                question="private",
                request_id="retention",
                status="COMPLETED",
            )
            for u, c in zip(users, conversations)
        ]
        owner.add_all(queries)
        await owner.flush()
        owner.add_all(
            [
                Message(conversation_id=c.id, query_id=q.id, role="user", content="private")
                for c, q in zip(conversations, queries)
            ]
        )
        await owner.commit()
        for user in users:
            owner.add(
                Evaluation(tenant_id=user.tenant_id, user_id=user.id, results={"marker": user.tenant_id})
            )
        await owner.commit()
        try:
            async with Runtime() as db:
                role = (
                    await db.execute(
                        text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
                    )
                ).one()
                assert role == (False, False)
                assert (await db.scalars(select(Document))).all() == []
            for user in users:
                async with Runtime(scope=Scope(user.tenant_id, user.id, user.role)) as db:
                    assert [d.tenant_id for d in (await db.scalars(select(Document))).all()] == [
                        user.tenant_id
                    ]
                    await db.commit()
                    assert [d.tenant_id for d in (await db.scalars(select(Document))).all()] == [
                        user.tenant_id
                    ]
                    other = next(t for t in tenants if t.id != user.tenant_id)
                    db.add(Document(tenant_id=other.id, name="attack.md", content_hash="x", size=1))
                    with pytest.raises(Exception, match="row-level security"):
                        await db.flush()
                    await db.rollback()
            async with Runtime() as db:
                assert (await db.scalars(select(Document))).all() == []
                with pytest.raises(Exception):
                    await db.execute(text("ALTER TABLE documents DISABLE ROW LEVEL SECURITY"))
                await db.rollback()

            async def runtime_db():
                async with Runtime() as db:
                    yield db

            app.dependency_overrides[get_db] = runtime_db
            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    for user in users:
                        headers = {"Authorization": "Bearer " + create_token(user)}
                        if user is users[0]:
                            locks = []
                            try:
                                for slot in range(2):
                                    connection = await engine.connect()
                                    await connection.execute(
                                        text("SELECT pg_advisory_lock(19471, :slot)"), {"slot": slot}
                                    )
                                    locks.append((slot, connection))
                                limited = await client.post(
                                    "/api/v1/chat", headers=headers, json={"question": "hi"}
                                )
                                assert limited.status_code == 429 and limited.headers["Retry-After"] == "5"
                            finally:
                                for slot, connection in locks:
                                    await connection.execute(
                                        text("SELECT pg_advisory_unlock(19471, :slot)"), {"slot": slot}
                                    )
                                    await connection.close()
                        response = await client.get("/api/v1/auth/me", headers=headers)
                        assert response.status_code == 200
                        result = await client.get("/api/v1/evaluation/results", headers=headers)
                        assert result.status_code == 200
                        assert [r["results"]["marker"] for r in result.json()] == [user.tenant_id]
                        own = next(c for c in conversations if c.tenant_id == user.tenant_id)
                        foreign = next(c for c in conversations if c.tenant_id != user.tenant_id)
                        assert (
                            await client.delete(f"/api/v1/conversations/{foreign.id}", headers=headers)
                        ).status_code == 404
                        assert (
                            await client.delete(f"/api/v1/conversations/{own.id}", headers=headers)
                        ).status_code == 204
                        assert not (
                            await owner.scalars(select(Query).where(Query.conversation_id == own.id))
                        ).all()
                        assert not (
                            await owner.scalars(select(Message).where(Message.conversation_id == own.id))
                        ).all()
                        assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 204
                        assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401
            finally:
                app.dependency_overrides.pop(get_db, None)
        finally:
            await runtime_engine.dispose()
            for t in tenants:
                await owner.execute(delete(Query).where(Query.tenant_id == t.id))
                await owner.execute(delete(Conversation).where(Conversation.tenant_id == t.id))
                await owner.execute(delete(Evaluation).where(Evaluation.tenant_id == t.id))
                await owner.execute(delete(Document).where(Document.tenant_id == t.id))
                await owner.execute(delete(User).where(User.tenant_id == t.id))
                await owner.delete(t)
            await owner.commit()
    await engine.dispose()
