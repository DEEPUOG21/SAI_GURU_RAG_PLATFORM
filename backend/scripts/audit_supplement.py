"""Read-only boundary probes and one evaluation against the existing synthetic test workspace."""

import asyncio
import json
from pathlib import Path

import system_smoke  # noqa: F401
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.agents.sql import sql_engine
from app.core.config import get_settings
from app.database.session import Session, engine
from app.main import app
from app.models.entities import User
from app.security.auth import create_token


async def main():
    assert get_settings().database_url.endswith("/sai_guru_test")
    results = {}
    spec = app.openapi()
    Path("docs/audit/openapi.json").write_text(json.dumps(spec, indent=2))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://audit") as client:
        codes = {}
        for path, methods in spec["paths"].items():
            for method, operation in methods.items():
                if not operation.get("security"):
                    continue
                url = path.replace("{id}", "missing").replace("{query_id}", "missing")
                response = await client.request(method.upper(), url)
                codes[method.upper() + " " + path] = response.status_code
        results["unauthenticated_endpoints"] = codes
        results["health"] = (await client.get("/api/v1/health")).status_code
        results["ready"] = (await client.get("/api/v1/ready")).status_code
        async with Session() as db:
            user = await db.scalar(select(User).where(User.email == get_settings().seed_admin_email))
        if user:
            response = await client.post(
                "/api/v1/evaluation/run", headers={"Authorization": "Bearer " + create_token(user)}
            )
            results["evaluation_http"] = response.status_code
            results["evaluation"] = response.json()
        else:
            results["evaluation"] = "NOT VERIFIED: seeded test account unavailable"
    sql = sql_engine()
    for name, statement in [
        ("private_table", "SELECT * FROM users LIMIT 0"),
        ("write", "DELETE FROM employees WHERE false"),
    ]:
        try:
            async with sql.begin() as connection:
                await connection.execute(text(statement))
            results["sql_" + name] = "FAIL: statement permitted"
        except Exception as exc:
            results["sql_" + name] = {"result": "denied", "exception_type": type(exc).__name__}
    await sql.dispose()
    await engine.dispose()
    Path("docs/audit/supplement.json").write_text(json.dumps(results, indent=2, default=str))
    print("Supplemental evidence saved; no credentials printed.")


if __name__ == "__main__":
    asyncio.run(main())
