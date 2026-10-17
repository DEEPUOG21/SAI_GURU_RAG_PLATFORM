"""Real PostgreSQL + real ONNX models. Run only against a disposable migrated test database."""

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text

from app.core.config import get_settings
from app.database.session import Session, engine
from app.ingestion.service import process, upload
from app.main import app
from app.models.entities import Chunk, Document, DocumentVersion, Message, Query, Tenant, User
from app.security.auth import passwords

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("SAI_INTEGRATION") != "1",
        reason="Set SAI_INTEGRATION=1 with a disposable migrated PostgreSQL database.",
    ),
]


async def test_real_end_to_end(monkeypatch):
    cfg = get_settings()
    assert cfg.database_url.split("?")[0].endswith("/sai_guru_test"), (
        "Integration tests require sai_guru_test."
    )
    monkeypatch.setattr(cfg, "jwt_secret", "integration-test-secret-" * 3)
    monkeypatch.setattr(cfg, "generation_mode", "extractive")
    suffix = uuid.uuid4().hex[:8]
    async with Session() as db:
        first, second = Tenant(name="Test A " + suffix), Tenant(name="Test B " + suffix)
        db.add_all([first, second])
        await db.flush()
        admin = User(
            tenant_id=first.id,
            email=f"admin-{suffix}@example.test",
            role="ADMIN",
            password_hash=passwords.hash("test-password-123"),
        )
        employee = User(
            tenant_id=first.id,
            email=f"employee-{suffix}@example.test",
            role="EMPLOYEE",
            password_hash=passwords.hash("test-password-123"),
        )
        outsider = User(
            tenant_id=second.id,
            email=f"other-{suffix}@example.test",
            role="ADMIN",
            password_hash=passwords.hash("test-password-123"),
        )
        db.add_all([admin, employee, outsider])
        await db.commit()
        doc = await upload(
            db,
            first.id,
            "Leave-Policy.md",
            b"# Annual leave\n\nEmployees receive 24 working days of annual leave.",
        )
        await process(db, doc)
        assert doc.status == "COMPLETED"
        chunk = await db.scalar(select(Chunk).where(Chunk.document_id == doc.id))
        assert len(chunk.embedding) == 384 and chunk.section == "Annual leave"
        assert chunk.page is None
        restricted = await upload(
            db, first.id, "Restricted.md", b"# Secret\n\nExecutive annual leave is 40 days.", min_role=2
        )
        await process(db, restricted)
        duplicate = await upload(
            db, first.id, doc.name, b"# Annual leave\n\nEmployees receive 24 working days of annual leave."
        )
        assert duplicate.version == 1

    async with AsyncClient(
        transport=ASGITransport(app=app, client=(f"test-{suffix}", 1)), base_url="http://test", timeout=180
    ) as client:
        tokens = {}
        for user in (admin, employee, outsider):
            response = await client.post(
                "/api/v1/auth/login", json={"email": user.email, "password": "test-password-123"}
            )
            assert response.status_code == 200, response.text
            tokens[user.role + user.tenant_id] = {
                "Authorization": "Bearer " + response.json()["access_token"]
            }
        a, e, o = tokens["ADMIN" + first.id], tokens["EMPLOYEE" + first.id], tokens["ADMIN" + second.id]
        assert (await client.get("/api/v1/ready")).status_code == 200
        assert (await client.get(f"/api/v1/documents/{doc.id}", headers=o)).status_code == 404
        assert (await client.get(f"/api/v1/documents/{restricted.id}", headers=e)).status_code == 404
        assert (await client.delete(f"/api/v1/documents/{doc.id}", headers=e)).status_code == 403
        assert (
            await client.post("/api/v1/documents", files={"file": ("x.txt", b"test")}, headers=e)
        ).status_code == 403
        assert (
            await client.post("/api/v1/documents", files={"file": ("x.exe", b"test")}, headers=a)
        ).status_code == 422
        chat = await client.post(
            "/api/v1/chat", headers=e, json={"question": "How much annual leave do employees receive?"}
        )
        assert chat.status_code == 200, chat.text
        import json

        frames = [json.loads(line[6:]) for line in chat.text.splitlines() if line.startswith("data: ")]
        final = next(frame for frame in frames if "answer" in frame)
        assert "24 working days" in final["answer"]
        assert "40 days" not in final["answer"]
        assert final["grounding"] == "SUPPORTED"
        assert all(c["document"] == "Leave-Policy.md" for c in final["citations"])
        query_id = final["query_id"]
        debug = await client.get(f"/api/v1/retrieval/debug/{query_id}", headers=e)
        assert debug.status_code == 200, debug.text
        candidate = debug.json()["candidates"][0]
        assert candidate["dense_score"] is not None and candidate["lexical_score"] is not None
        assert candidate["rrf_score"] > 0 and candidate["reranker_score"] is not None
        assert (await client.get(f"/api/v1/retrieval/debug/{query_id}", headers=o)).status_code == 404
        assert (
            await client.post("/api/v1/feedback", headers=e, json={"query_id": query_id, "rating": 1})
        ).status_code == 200
        dashboard = (await client.get("/api/v1/dashboard", headers=e)).json()
        assert dashboard["documents_indexed"] == 1
        assert dashboard["total_queries"] == 1 and dashboard["successful_queries"] == 1
        conversation_id = next(frame["conversation_id"] for frame in frames if "conversation_id" in frame)
        # A later uncited response can depend on earlier private sources through conversation history.
        async with Session() as history_db:
            derived = Query(
                tenant_id=first.id,
                user_id=employee.id,
                conversation_id=conversation_id,
                question="Explain that",
                request_id="test-history",
                status="COMPLETED",
                trace=[{"node": "history_sources", "output": final["citations"]}],
            )
            history_db.add(derived)
            await history_db.flush()
            history_db.add(
                Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content="Derived private explanation",
                    citations=[],
                    query_id=derived.id,
                )
            )
            await history_db.commit()
        assert (
            await client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=o)
        ).status_code == 404
        assert (await client.delete(f"/api/v1/documents/{doc.id}", headers=a)).status_code == 204
        history = (await client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=e)).json()
        assert history == []  # Document deletion now erases derived messages, not just redacts them.
        from app.security.scope import Scope
        from app.services.chat import conversation_history

        async with Session() as history_db:
            model_history = await conversation_history(
                history_db, conversation_id, Scope(first.id, employee.id, "EMPLOYEE")
            )
        assert not any("24 working days" in message["content"] for message in model_history)
        assert not any("Derived private explanation" in message["content"] for message in model_history)
        assert model_history == []
        assert (await client.get(f"/api/v1/retrieval/debug/{query_id}", headers=e)).status_code == 404
        assert (await client.get(f"/api/v1/retrieval/debug/{derived.id}", headers=e)).status_code == 404

    async with Session() as db:
        assert await db.scalar(select(Chunk).where(Chunk.document_id == doc.id)) is None
        assert await db.scalar(select(DocumentVersion).where(DocumentVersion.document_id == doc.id)) is None
        replacement = await upload(
            db, first.id, restricted.name, b"# Secret\n\nExecutive annual leave is 41 days.", min_role=2
        )
        assert replacement.version == 2
        assert await db.scalar(select(Chunk).where(Chunk.document_id == restricted.id)) is None
        await process(db, replacement)
        assert (await db.scalar(select(Chunk).where(Chunk.document_id == restricted.id))).version == 2
        # Test only: remove this test's two tenants and dependent rows, never preexisting data.
        for tenant in (first, second):
            await db.execute(
                text("DELETE FROM feedback WHERE user_id IN (SELECT id FROM users WHERE tenant_id=:t)"),
                {"t": tenant.id},
            )
            await db.execute(text("DELETE FROM queries WHERE tenant_id=:t"), {"t": tenant.id})
            await db.execute(text("DELETE FROM conversations WHERE tenant_id=:t"), {"t": tenant.id})
            await db.execute(delete(Document).where(Document.tenant_id == tenant.id))
            await db.execute(delete(User).where(User.tenant_id == tenant.id))
            await db.execute(delete(Tenant).where(Tenant.id == tenant.id))
        await db.commit()
    await engine.dispose()
