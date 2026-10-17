"""Cross-process admission control held until the complete response/stream closes."""

import asyncio

import jwt
from sqlalchemy import text
from starlette.responses import JSONResponse

from app.database.session import engine
from app.security.auth import decode_token


class CapacityMiddleware:
    def __init__(self, app, slots=2):
        self.app, self.slots, self.active = app, slots, 0

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        expensive = scope.get("method") == "POST" and (
            path in {"/api/v1/chat", "/api/v1/documents", "/api/v1/evaluation/run"}
            or path.startswith("/api/v1/documents/")
            and path.endswith("/process")
        )
        if not expensive:
            return await self.app(scope, receive, send)
        authorization = dict(scope.get("headers", [])).get(b"authorization", b"").decode("latin1")
        try:
            if not authorization.startswith("Bearer "):
                raise jwt.InvalidTokenError()
            decode_token(authorization[7:])
        except jwt.PyJWTError:
            response = JSONResponse({"error": {"message": "Sign in to continue."}}, status_code=401)
            return await response(scope, receive, send)
        if self.active >= self.slots:
            return await self.reject(scope, receive, send)
        self.active += 1
        connection, acquired = None, None
        try:
            async with asyncio.timeout(3):
                connection = await engine.connect()
                for slot in range(self.slots):
                    if await connection.scalar(
                        text("SELECT pg_try_advisory_lock(19471, :slot)"), {"slot": slot}
                    ):
                        acquired = slot
                        break
            if acquired is None:
                return await self.reject(scope, receive, send)
            await self.app(scope, receive, send)
        finally:
            try:
                if connection is not None:
                    if acquired is not None:
                        await connection.execute(
                            text("SELECT pg_advisory_unlock(19471, :slot)"), {"slot": acquired}
                        )
                    await connection.close()
            except BaseException:
                if connection is not None:
                    await connection.invalidate()
                raise
            finally:
                self.active -= 1

    async def reject(self, scope, receive, send):
        response = JSONResponse(
            {"error": {"message": "The service is busy. Retry shortly."}},
            status_code=429,
            headers={"Retry-After": "5"},
        )
        await response(scope, receive, send)
