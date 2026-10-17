"""Provision a non-owner runtime role using migration-owner DATABASE_URL."""

import asyncio
import os
import re

from dotenv import load_dotenv
from sqlalchemy import text

from app.database.session import engine


async def main():
    load_dotenv()
    password = os.environ.get("RUNTIME_DATABASE_PASSWORD", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", password):
        raise ValueError("Set RUNTIME_DATABASE_PASSWORD to 32–128 random URL-safe characters.")
    try:
        async with engine.begin() as connection:
            if not await connection.scalar(text("SELECT 1 FROM pg_roles WHERE rolname='sai_runtime'")):
                await connection.execute(
                    text(
                        "CREATE ROLE sai_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                    )
                )
            unsafe = await connection.scalar(
                text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname='sai_runtime'")
            )
            if unsafe:
                raise RuntimeError("Refusing a privileged existing runtime role.")
            # Managed Postgres owners cannot ALTER SUPERUSER/BYPASSRLS attributes,
            # even to false. Verify those flags instead of trying to change them.
            await connection.execute(text("ALTER ROLE sai_runtime NOCREATEDB NOCREATEROLE NOINHERIT"))
            await connection.execute(text(f"ALTER ROLE sai_runtime PASSWORD '{password}'"))
            await connection.execute(text("GRANT USAGE ON SCHEMA public TO sai_runtime"))
            await connection.execute(
                text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sai_runtime")
            )
            await connection.execute(text("REVOKE ALL ON alembic_version FROM sai_runtime"))
            await connection.execute(text("REVOKE INSERT, UPDATE, DELETE ON employees FROM sai_runtime"))
            if await connection.scalar(text("SELECT to_regclass('public.employee_analytics')")):
                await connection.execute(
                    text("REVOKE INSERT, UPDATE, DELETE ON employee_analytics FROM sai_runtime")
                )
            await connection.execute(text("GRANT SELECT ON alembic_version TO sai_runtime"))
            await connection.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC, sai_runtime"))
    except Exception:
        # DDL exception text can contain its password literal; never propagate it.
        raise RuntimeError(
            "Runtime role setup failed; verify owner privileges and database connectivity."
        ) from None
    finally:
        await engine.dispose()
    print("Runtime role provisioned. Configure the API DATABASE_URL with sai_runtime, not the owner.")


if __name__ == "__main__":
    asyncio.run(main())
