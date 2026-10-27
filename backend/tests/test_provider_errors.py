import json

import httpx
import pytest

from app.observability.trace import Trace
from app.services.provider_errors import cloudflare_error_codes, safe_provider_error_message


def provider_error(code, message="private detail"):
    response = httpx.Response(429, json={"success": False, "errors": [{"code": code, "message": message}]})
    return httpx.HTTPStatusError(
        "upstream rate limit", request=httpx.Request("POST", "https://provider.invalid"), response=response
    )


@pytest.mark.parametrize(
    "code,expected",
    [
        (3036, "Today's free AI usage has been reached. It resets at 00:00 UTC; please try again after then."),
        (3040, "The AI service is temporarily at capacity. Please try again shortly."),
        (9999, "The AI service is rate-limited right now. Please try again shortly."),
    ],
)
def test_rate_limit_message_classifies_cloudflare_code_without_exposing_provider_text(code, expected):
    error = provider_error(code)
    assert cloudflare_error_codes(error) == [code]
    message = safe_provider_error_message(error)
    assert message == expected
    assert "private detail" not in message


async def test_trace_does_not_retry_429_and_keeps_only_safe_provider_code():
    trace, calls = Trace(), 0
    error = provider_error(3036)

    async def failed_call():
        nonlocal calls
        calls += 1
        raise error

    with pytest.raises(httpx.HTTPStatusError):
        await trace.run("generation", failed_call, retries=3)

    assert calls == 1
    assert trace.steps == [
        {
            "node": "generation",
            "status": "failed",
            "error": "HTTPStatusError",
            "attempts": 1,
            "latency_ms": trace.steps[0]["latency_ms"],
            "http_status": 429,
            "provider_error_codes": [3036],
        }
    ]
    assert "private detail" not in json.dumps(trace.steps)
