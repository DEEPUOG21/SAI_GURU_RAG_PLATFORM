import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.agents.sql import validate_sql
from app.core.config import Settings, get_settings
from app.main import app
from app.security.auth import create_token, decode_token, passwords
from app.security.body_limit import BodyLimitMiddleware


@pytest.mark.parametrize(
    "change", ["expired", "unsigned", "wrong_algorithm", "wrong_audience", "missing_exp"]
)
def test_reject_bad_jwt(monkeypatch, change):
    key = "audit-only-signing-key-" * 3
    monkeypatch.setattr(get_settings(), "jwt_secret", key)
    claims = jwt.decode(
        create_token(SimpleNamespace(id="audit")), key, algorithms=["HS256"], audience="sai-guru-web"
    )
    algorithm = "HS256"
    if change == "expired":
        claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    if change == "unsigned":
        algorithm, key = "none", None
    if change == "wrong_algorithm":
        algorithm = "HS384"
    if change == "wrong_audience":
        claims["aud"] = "attacker"
    if change == "missing_exp":
        del claims["exp"]
    with pytest.raises(jwt.PyJWTError):
        decode_token(jwt.encode(claims, key, algorithm=algorithm))


def test_password_hash_is_argon2_and_verifies():
    value = passwords.hash("audit-only-password")
    assert value.startswith("$argon2") and "audit-only-password" not in value
    assert passwords.verify("audit-only-password", value)
    assert not passwords.verify("wrong", value)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO employees VALUES (1)",
        "UPDATE employees SET department='x'",
        "DROP TABLE employees",
        "ALTER TABLE employees ADD x int",
        "TRUNCATE employees",
        "CREATE TABLE x (id int)",
        "GRANT ALL ON employees TO PUBLIC",
        "REVOKE SELECT ON employees FROM PUBLIC",
        "SELECT * FROM employees WHERE tenant_id='x' OR 1=1",
    ],
)
def test_sql_attack_allowlist(sql):
    with pytest.raises(ValueError):
        validate_sql(sql)


@pytest.mark.parametrize(
    "origin",
    ["*", "https://*.example.com", "https://user:pass@example.com", "https://example.com/path", "null"],
)
def test_unsafe_cors_configuration_rejected(origin):
    with pytest.raises(ValidationError):
        Settings(cors_origins=origin)


async def test_security_headers_and_rejected_origin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/health", headers={"Origin": "https://attacker.example"})
    assert "access-control-allow-origin" not in r.headers
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"


async def test_slow_body_deadline():
    sent = []

    async def receive():
        await asyncio.sleep(1)
        return {"type": "http.request", "body": b"", "more_body": True}

    async def send(frame):
        sent.append(frame)

    async def downstream(*args):
        raise AssertionError("slow request reached application")

    await BodyLimitMiddleware(downstream, 100, timeout=0.01)(
        {"type": "http", "method": "POST", "state": {}}, receive, send
    )
    assert sent[0]["status"] == 408


async def test_fragmented_body_is_coalesced():
    count = 0

    async def receive():
        nonlocal count
        count += 1
        return {"type": "http.request", "body": b"x", "more_body": count < 1000}

    async def downstream(scope, receive, send):
        frame = await receive()
        assert frame["body"] == b"x" * 1000 and frame["more_body"] is False

    await BodyLimitMiddleware(downstream, 1000)({"type": "http", "method": "POST"}, receive, None)
def test_docx_expansion_limit():
    import io
    import zipfile

    from app.ingestion.parsing import validate_file

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as doc:
        doc.writestr("word/document.xml", b"x" * (41 * 1024 * 1024))
    assert len(archive.getvalue()) < 10 * 1024 * 1024
    with pytest.raises(ValueError, match="Expanded DOCX"):
        validate_file("bomb.docx", archive.getvalue())
