
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from app.api import auth
from app.core.config import get_settings
from app.database.session import get_db
from app.main import app
from app.models.entities import Tenant, User
from app.security.auth import decode_token, passwords


@pytest.fixture
def registration(monkeypatch):
    calls = {"scope": {}, "added": [], "commits": 0, "rollbacks": 0, "duplicate": False}

    class DB:
        def add(self, item):
            calls["added"].append(item)

        async def flush(self):
            if calls["duplicate"] and isinstance(calls["added"][-1], User):
                raise IntegrityError("insert", {}, Exception("unique email"))

        async def commit(self):
            calls["commits"] += 1

        async def rollback(self):
            calls["rollbacks"] += 1

    async def dependency():
        yield DB()

    async def bind(db, **scope):
        calls["scope"].update(scope)

    async def limited(db, key, limit):
        calls["rate_limit"] = (key, limit)

    monkeypatch.setattr(auth, "bind_scope", bind)
    monkeypatch.setattr(auth, "rate_limit", limited)
    monkeypatch.setattr(get_settings(), "jwt_secret", "signup-test-secret-" * 3)
    app.dependency_overrides[get_db] = dependency
    yield calls
    app.dependency_overrides.pop(get_db, None)


BODY = {"email": "New@User.test", "password": "a-long-signup-password", "workspace_name": "New team"}


async def test_signup_creates_only_a_fresh_workspace_and_hashes_password(registration):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/signup", json=BODY)
    assert response.status_code == 201
    tenant, user = registration["added"]
    assert isinstance(tenant, Tenant) and isinstance(user, User)
    assert user.tenant_id == tenant.id == registration["scope"]["tenant_id"]
    assert user.id == registration["scope"]["user_id"]
    assert user.role == "ADMIN" and user.email == "new@user.test"
    assert passwords.verify(BODY["password"], user.password_hash)
    assert decode_token(response.json()["access_token"])["sub"] == user.id
    assert registration["commits"] == 1 and registration["rate_limit"][1] == 5


async def test_duplicate_signup_rolls_back_workspace_and_user_together(registration):
    registration["duplicate"] = True
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/signup", json=BODY)
    assert response.status_code == 409
    assert registration["rollbacks"] == 1 and registration["commits"] == 0
    assert "access_token" not in response.json()


@pytest.mark.parametrize(
    "change",
    [{"tenant_id": "existing"}, {"role": "ADMIN"}, {"password": "short"}, {"workspace_name": "  "}, {"email": "invalid"}],
)
async def test_signup_rejects_access_overrides_and_invalid_fields(registration, change):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/signup", json={**BODY, **change})
    assert response.status_code == 422
    assert registration["added"] == []
