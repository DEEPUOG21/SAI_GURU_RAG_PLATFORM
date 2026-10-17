import asyncio
import time


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
        for attempt in range(retries + 1):
            try:
                async with asyncio.timeout(timeout):
                    result = await operation()
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
