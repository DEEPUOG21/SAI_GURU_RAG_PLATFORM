import hashlib
import time
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.database.session import bind_scope, get_db
from app.models.entities import RateLimit, User
from app.security.scope import Scope

passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def secret():
    value = get_settings().jwt_secret
    if len(value) < 32:
        raise HTTPException(
            503, "Set JWT_SECRET to a cryptographically random value of at least 32 characters."
        )
    return value


def create_token(user):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user.id,
            "ver": getattr(user, "token_version", 0),
            "iat": now,
            "exp": now + timedelta(hours=1),
            "iss": "sai-guru",
            "aud": "sai-guru-web",
        },
        secret(),
        algorithm="HS256",
    )


def decode_token(token):
    return jwt.decode(
        token,
        secret(),
        algorithms=["HS256"],
        issuer="sai-guru",
        audience="sai-guru-web",
        options={"require": ["exp", "iat", "sub"]},
    )


async def current_scope(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)
):
    if not credentials:
        raise HTTPException(401, "Sign in to continue.")
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Session expired or invalid. Sign in again.") from exc
    await bind_scope(db, user_id=payload["sub"])
    user = await db.scalar(select(User).where(User.id == payload["sub"]))
    if not user:
        raise HTTPException(401, "User no longer exists.")
    if payload.get("ver", 0) != user.token_version:
        raise HTTPException(401, "Session revoked. Sign in again.")
    await bind_scope(db, tenant_id=user.tenant_id)
    return Scope(user.tenant_id, user.id, user.role)


def require_role(scope, level):
    if scope.level < level:
        raise HTTPException(403, "Your role does not permit this action.")


async def rate_limit(db, key, limit=None):
    window = int(time.time() // 60)
    hashed = hashlib.sha256(key.encode()).hexdigest()
    statement = (
        insert(RateLimit)
        .values(key=hashed, window=window, count=1)
        .on_conflict_do_update(
            index_elements=[RateLimit.key, RateLimit.window], set_={"count": RateLimit.count + 1}
        )
        .returning(RateLimit.count)
    )
    count = await db.scalar(statement)
    await db.execute(delete(RateLimit).where(RateLimit.window < window - 2))
    await db.commit()
    if count > (limit or get_settings().rate_limit_per_minute):
        raise HTTPException(429, "Too many requests. Try again in a minute.", headers={"Retry-After": "60"})
