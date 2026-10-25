import asyncio
import time

from langsmith import traceable


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
                if attempt == retries:
                    self.steps.append(
                        {
                            "node": node,
                            "status": "failed",
                            "error": type(exc).__name__,
                            "attempts": attempt + 1,
                            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                        }
                    )
                    raise
                await asyncio.sleep(0.25 * (attempt + 1))

    def record(self, node, output, status="completed"):
        self.iterations += 1
        if self.iterations > 24:
            raise RuntimeError("Workflow exceeded 24 nodes.")
        self.steps.append({"node": node, "status": status, "output": output})
