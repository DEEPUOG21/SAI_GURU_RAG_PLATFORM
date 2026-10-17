"""Read-only deployed database checks and real API login using private local config."""

import asyncio
import json
import os
from pathlib import Path

import asyncpg
from dotenv import dotenv_values
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]


async def main():
    os.chdir(ROOT)
    values = dotenv_values(".env.supabase", interpolate=False)
    os.environ.update(values)
    os.environ["PGSSLROOTCERT"] = str(ROOT / ".env.supabase-ca.crt")
    from app.database.session import engine
    from app.main import app, lifespan

    result = {}
    async with lifespan(app):
        async with engine.connect() as connection:
            result["runtime_role"] = dict(
                (
                    await connection.execute(
                        text(
                            "SELECT rolname, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole "
                            "FROM pg_roles WHERE rolname=current_user"
                        )
                    )
                )
                .mappings()
                .one()
            )
            result["unscoped_documents"] = await connection.scalar(text("SELECT count(*) FROM documents"))
            assert result["unscoped_documents"] == 0
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": values["SEED_ADMIN_EMAIL"], "password": values["SEED_ADMIN_PASSWORD"]},
            )
            result["login_status"] = login.status_code
            assert login.status_code == 200
            headers = {"Authorization": "Bearer " + login.json()["access_token"]}
            profile = await client.get("/api/v1/auth/me", headers=headers)
            assert profile.status_code == 200
            async with engine.connect() as connection:
                await connection.execute(
                    text("SELECT set_config('app.user_id', :id, true)"), {"id": profile.json()["id"]}
                )
                tenant = await connection.scalar(
                    text("SELECT tenant_id FROM users WHERE id=:id"), {"id": profile.json()["id"]}
                )
            docs = await client.get("/api/v1/documents", headers=headers)
            result["documents_status"] = docs.status_code
            result["documents_count"] = len(docs.json())
            assert docs.status_code == 200 and result["documents_count"] == 8
            result["document_states"] = sorted({d["status"] for d in docs.json()})
    reader_url = make_url(values["SQL_DATABASE_URL"]).set(drivername="postgresql")
    reader = await asyncpg.connect(
        reader_url.render_as_string(hide_password=False), timeout=15, command_timeout=15
    )
    try:
        result["reader_read_only"] = await reader.fetchval("SHOW default_transaction_read_only")
        await reader.execute("SELECT set_config('app.tenant_id', $1, false)", tenant)
        result["scoped_employee_count"] = await reader.fetchval("SELECT count(*) FROM employee_analytics")
        assert result["scoped_employee_count"] == 8
        await reader.execute("SELECT set_config('app.tenant_id', 'unrelated-tenant', false)")
        result["other_tenant_employee_count"] = await reader.fetchval(
            "SELECT count(*) FROM employee_analytics"
        )
        assert result["other_tenant_employee_count"] == 0
        try:
            await reader.fetchval("SELECT count(*) FROM users")
        except asyncpg.InsufficientPrivilegeError:
            result["reader_users_access"] = "DENIED"
        else:
            raise AssertionError("Reader accessed users")
    finally:
        await reader.close()
    Path("docs/audit/supabase-runtime-verification.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print("Verification failed:", type(exc).__name__)
        raise SystemExit(1) from None
