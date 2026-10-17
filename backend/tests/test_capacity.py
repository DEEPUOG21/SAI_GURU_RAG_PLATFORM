from app.security.capacity import CapacityMiddleware


async def test_overloaded_request_is_rejected_without_reading_body_or_calling_database(monkeypatch):
    monkeypatch.setattr("app.security.capacity.decode_token", lambda token: {"sub": "test"})

    async def forbidden(*args):
        raise AssertionError("Overloaded request reached downstream")

    sent = []

    async def send(message):
        sent.append(message)

    middleware = CapacityMiddleware(forbidden, slots=2)
    middleware.active = 2
    await middleware(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/chat",
            "headers": [(b"authorization", b"Bearer test")],
        },
        forbidden,
        send,
    )
    assert sent[0]["status"] == 429
    assert (b"retry-after", b"5") in sent[0]["headers"]


async def test_anonymous_requests_cannot_reserve_expensive_slots():
    async def forbidden(*args):
        raise AssertionError("Anonymous request reserved resources")

    sent = []

    async def send(message):
        sent.append(message)

    middleware = CapacityMiddleware(forbidden)
    await middleware({"type": "http", "method": "POST", "path": "/api/v1/chat"}, forbidden, send)
    assert sent[0]["status"] == 401 and middleware.active == 0
