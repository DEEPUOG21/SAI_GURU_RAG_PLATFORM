from httpx import ASGITransport, AsyncClient
from starlette.responses import PlainTextResponse

from app.security.body_limit import BodyLimitMiddleware


async def test_streamed_body_limited_without_content_length():
    called = []

    async def downstream(scope, receive, send):
        called.append(True)
        await PlainTextResponse("ok")(scope, receive, send)

    async def body():
        yield b"12345"
        yield b"67890"

    async with AsyncClient(
        transport=ASGITransport(app=BodyLimitMiddleware(downstream, limit=6)), base_url="http://test"
    ) as client:
        response = await client.post("/upload", content=body())
    assert response.status_code == 413 and not called
