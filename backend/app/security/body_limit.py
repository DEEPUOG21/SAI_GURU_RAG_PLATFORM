import asyncio

from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    """Bound request bytes before multipart parsing can spool an oversized upload to disk."""

    def __init__(self, app, limit, timeout=15):
        self.app, self.limit, self.timeout = app, limit, timeout

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        body = bytearray()
        limit = self.limit if scope.get("path") == "/api/v1/documents" else min(self.limit, 65536)
        error, status = None, None
        try:
            async with asyncio.timeout(self.timeout):
                while True:
                    frame = await receive()
                    if frame["type"] == "http.disconnect":
                        return
                    chunk = frame.get("body", b"")
                    if len(body) + len(chunk) > limit:
                        error, status = "Request body exceeds the upload limit.", 413
                        break
                    body.extend(chunk)
                    if not frame.get("more_body", False):
                        break
        except TimeoutError:
            error, status = "Request body timed out.", 408
        if error:
            response = JSONResponse(
                {"error": {"message": error, "request_id": scope.get("state", {}).get("request_id")}},
                status_code=status,
            )
            return await response(scope, receive, send)
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
