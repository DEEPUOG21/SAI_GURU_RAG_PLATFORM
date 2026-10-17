from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app
from app.security.auth import create_token, decode_token, require_role
from app.security.scope import Scope


@pytest.mark.parametrize(
    "path", ["/api/v1/documents", "/api/v1/conversations", "/api/v1/dashboard", "/api/v1/auth/me"]
)
async def test_authentication_required(path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)
    assert response.status_code == 401
    assert "error" in response.json()


def test_jwt_signature(monkeypatch):
    monkeypatch.setattr(get_settings(), "jwt_secret", "test-only-" * 5)
    token = create_token(SimpleNamespace(id="user"))
    assert decode_token(token)["sub"] == "user"
    with pytest.raises(jwt.PyJWTError):
        decode_token(token[:-5] + "wrong")


def test_no_default_secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "jwt_secret", "")
    with pytest.raises(HTTPException) as exc:
        create_token(SimpleNamespace(id="user"))
    assert exc.value.status_code == 503


def test_role_access():
    with pytest.raises(HTTPException):
        require_role(Scope("t", "u", "EMPLOYEE"), 1)
    require_role(Scope("t", "u", "MANAGER"), 1)
    with pytest.raises(HTTPException):
        require_role(Scope("t", "u", "MANAGER"), 2)
