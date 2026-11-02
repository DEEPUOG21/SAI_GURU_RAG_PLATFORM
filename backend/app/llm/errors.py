"""Safe classification of upstream AI service failures."""

import httpx


def cloudflare_error_codes(error):
    response = getattr(error, "response", None)
    if not isinstance(response, httpx.Response):
        return []
    try:
        payload = response.json()
    except (ValueError, UnicodeDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    rows = payload.get("errors", [])
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        return []
    return sorted(
        {
            row["code"]
            for row in rows
            if isinstance(row, dict) and type(row.get("code")) is int and 0 < row["code"] < 100_000
        }
    )


def safe_provider_error_message(error):
    if isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 429:
        codes = cloudflare_error_codes(error)
        if 3036 in codes:
            return "Today's free AI usage has been reached. It resets at 00:00 UTC; please try again after then."
        if 3040 in codes:
            return "The AI service is temporarily at capacity. Please try again shortly."
        return "The AI service is rate-limited right now. Please try again shortly."
    return "The request could not be completed right now. Please try again later."
