"""Run with the migration owner credentials; the API never calls this module."""

import asyncio
import os
import re

from dotenv import load_dotenv
from sqlalchemy import text

from app.database.session import engine


async def main():
    load_dotenv()
    password = os.environ.get("SQL_READER_PASSWORD", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,128}", password):
        raise ValueError("Set SQL_READER_PASSWORD to 24–128 random letters, digits, hyphens or underscores.")
    async with engine.begin() as connection:
        exists = await connection.scalar(text("SELECT 1 FROM pg_roles WHERE rolname='sai_reader'"))
        if not exists:
            await connection.execute(
                text("CREATE ROLE sai_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS")
            )
        # The restricted character allowlist above makes this DDL literal safe; SQL cannot bind role passwords.
        await connection.execute(text(f"ALTER ROLE sai_reader PASSWORD '{password}'"))
        await connection.execute(text("ALTER ROLE sai_reader SET default_transaction_read_only = on"))
        await connection.execute(
            text(
                "CREATE OR REPLACE VIEW employee_analytics WITH (security_barrier=true) AS "
                "SELECT department, joined_at FROM employees "
                "WHERE tenant_id = current_setting('app.tenant_id', true)"
            )
        )
        await connection.execute(text("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM sai_reader"))
        await connection.execute(text("GRANT USAGE ON SCHEMA public TO sai_reader"))
        await connection.execute(text("GRANT SELECT ON employee_analytics TO sai_reader"))
        await connection.execute(text("REVOKE ALL ON employee_analytics FROM PUBLIC"))
        for role in ("anon", "authenticated"):
            if await connection.scalar(text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}):
                await connection.execute(text(f"REVOKE ALL ON employee_analytics FROM {role}"))
    await engine.dispose()
    print("Read-only analytics role configured. Set SQL_DATABASE_URL with the sai_reader credentials.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        raise SystemExit("SQL reader setup failed; verify owner privileges and configuration.") from None
