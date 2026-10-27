import asyncio
import time

import httpx
from langsmith import traceable

from app.security.guardrails import redact_value
from app.services.provider_errors import cloudflare_error_codes


class Trace:
    def __init__(self):
        self.steps = []
        self.candidates = []
        self.iterations = 0

    async def run(self, node, operation, *, timeout=60, retries=0):
        self.iterations += 1
        if self.iterations > 24:
            raise RuntimeError("Workflow exceeded 24 nodes.")
        start = time.perf_counter()

        @traceable(name=node, run_type="chain")
        async def traced_operation():
            return await operation()

        for attempt in range(retries + 1):
            try:
                async with asyncio.timeout(timeout):
                    # A child span for each actual attempt; existing local trace remains authoritative.
                    result = await traced_operation()
                self.steps.append(
                    {
                        "node": node,
                        "status": "completed",
                        "attempts": attempt + 1,
                        "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                    }
                )
                return result
            except Exception as exc:
                step = {
                    "node": node,
                    "status": "failed",
                    "error": type(exc).__name__,
                    "attempts": attempt + 1,
                    "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                }
                if isinstance(exc, httpx.HTTPStatusError):
                    step["http_status"] = exc.response.status_code
                    codes = cloudflare_error_codes(exc)
                    if codes:
                        step["provider_error_codes"] = codes
                # A 429 never improves through an immediate retry; it may be a daily
                # account allowance or provider capacity limit.
                if attempt == retries or (
                    isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429
                ):
                    self.steps.append(step)
                    raise
                await asyncio.sleep(0.25 * (attempt + 1))

    def record(self, node, output, status="completed"):
        self.iterations += 1
        if self.iterations > 24:
            raise RuntimeError("Workflow exceeded 24 nodes.")
        self.steps.append({"node": node, "status": status, "output": redact_value(output)})

    def guardrail(self, stage, metadata):
        # Policy checkpoints do not consume the existing tool/retry budget.
        if sum(step["node"].startswith("guardrail_") for step in self.steps) >= 12:
            raise RuntimeError("Guardrail checkpoint budget exceeded.")
        self.steps.append({"node": "guardrail_" + stage, "status": "completed", "output": metadata})
