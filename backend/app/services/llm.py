import json
import math
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import httpx
from langsmith import traceable

from app.core.config import get_settings


class LLMProvider(ABC):
    @abstractmethod
    def stream(self, messages: list[dict], *, json_mode: bool | dict = False) -> AsyncIterator[dict]: ...

    async def complete(self, messages: list[dict], *, json_mode: bool | dict = False):
        parts, usage = [], None
        async for event in self.stream(messages, json_mode=json_mode):
            if event.get("text"):
                parts.append(event["text"])
            if event.get("usage"):
                usage = event["usage"]
        return "".join(parts), usage


def model_trace_output(events):
    """Use the provider's usage, never a fabricated token estimate."""
    output = {
        "choices": [{"message": {"role": "assistant", "content": "".join(e.get("text", "") for e in events)}}]
    }
    usage = next((e["usage"] for e in reversed(events) if e.get("usage")), None)
    if usage:
        output["usage"] = usage
    return output


class TrackedLLM(LLMProvider):
    """Record one usage report per call, including missing reports."""

    def __init__(self, provider):
        self.provider = provider
        self.usages = []

    async def stream(self, messages, *, json_mode=False):
        usage = None
        completed = False
        cfg = get_settings()

        @traceable(
            name="model_completion",
            run_type="llm",
            reduce_fn=model_trace_output,
            metadata={"ls_provider": cfg.llm_provider, "ls_model_name": cfg.llm_model},
        )
        async def traced_stream(messages):
            async for event in self.provider.stream(messages, json_mode=json_mode):
                yield event

        try:
            async for event in traced_stream(messages):
                if event.get("usage"):
                    usage = event["usage"]
                yield event
            completed = True
        finally:
            self.usages.append(usage if completed else None)


class OpenCompatibleLLM(LLMProvider):
    """Works with Ollama's local OpenAI-compatible endpoint; paid keys are optional."""

    async def stream(self, messages, *, json_mode=False):
        cfg = get_settings()
        headers = {"Authorization": f"Bearer {cfg.llm_api_key}"} if cfg.llm_api_key else {}
        payload = {
            "model": cfg.llm_model,
            "messages": messages,
            "stream": True,
            "temperature": 0,
            "max_tokens": 1000,
            "stream_options": {"include_usage": True},
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if json_mode and cfg.llm_provider == "cloudflare":
            # Workers AI requires an explicit schema and non-streaming JSON mode.
            if not isinstance(json_mode, dict):
                raise ValueError("Cloudflare JSON mode requires a schema.")
            payload["stream"] = False
            payload.pop("stream_options")
            payload["response_format"] = {"type": "json_schema", "json_schema": json_mode}
            async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as client:
                response = await client.post(
                    cfg.llm_url.rstrip("/") + "/chat/completions", json=payload, headers=headers
                )
                response.raise_for_status()
            event = response.json()
            choice = event["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ValueError("LLM generation ended without a complete answer.")
            content = choice["message"]["content"]
            if not isinstance(content, str) or not isinstance(json.loads(content), dict):
                raise ValueError("Malformed LLM JSON response.")
            yield {"text": content, "usage": event.get("usage")}
            return
        completed = False
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10)) as client:
            async with client.stream(
                "POST", cfg.llm_url.rstrip("/") + "/chat/completions", json=payload, headers=headers
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        completed = True
                        break
                    try:
                        event = json.loads(raw)
                        if "error" in event:
                            raise ValueError("Provider returned a stream error.")
                        choices = event.get("choices", [])
                        if choices and choices[0].get("finish_reason") not in (None, "stop"):
                            raise ValueError("LLM generation ended without a complete answer.")
                        delta = choices[0].get("delta", {}) if choices else {}
                        content = delta.get("content")
                        if content is None:
                            content = ""
                        # Workers AI may encode numeric token fragments as JSON numbers,
                        # including zero. Preserve them rather than dropping falsey values.
                        if cfg.llm_provider == "cloudflare" and type(content) in (int, float):
                            if not math.isfinite(content):
                                raise ValueError("Invalid numeric LLM fragment.")
                            content = str(content)
                        if not isinstance(content, str):
                            raise ValueError("Malformed LLM content fragment.")
                        yield {"text": content, "usage": event.get("usage")}
                    except (json.JSONDecodeError, TypeError, KeyError) as exc:
                        raise ValueError("Malformed LLM stream.") from exc
        if not completed:
            raise ValueError("LLM stream ended before completion.")


def llm() -> LLMProvider:
    return OpenCompatibleLLM()
