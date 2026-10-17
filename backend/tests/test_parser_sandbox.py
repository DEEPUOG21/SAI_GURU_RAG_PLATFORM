import pytest

from app.ingestion.sandbox import parse_isolated


async def test_isolated_parser_returns_text():
    result = await parse_isolated("example.md", b"# Heading\n\nA supported fact.")
    assert result[0].text == "A supported fact."


async def test_isolated_parser_rejects_malformed_document():
    with pytest.raises(ValueError, match="parser rejected"):
        await parse_isolated("broken.json", b"{broken")


async def test_isolated_parser_deadline_terminates_child():
    import asyncio

    with pytest.raises(asyncio.TimeoutError):
        await parse_isolated("example.md", b"hello", timeout=0.001)
