"""Provision the explicitly selected Sai Guru Supabase project without logging secrets."""

import asyncio
import json
import os
import secrets
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]
PROJECT = os.environ.get("SUPABASE_PROJECT_REF", "")
HOST = os.environ.get("SUPABASE_POOLER_HOST", "")


def database_url(role, password):
    return URL.create(
        "postgresql+asyncpg",
        username=f"{role}.{PROJECT}",
        password=password,
        host=HOST,
        port=5432,
        database="postgres",
        query={"ssl": "verify-full"},
    ).render_as_string(hide_password=False)


async def main():
    os.chdir(ROOT)
    if not PROJECT or not HOST:
        raise SystemExit("Set SUPABASE_PROJECT_REF and SUPABASE_POOLER_HOST from your project Connect dialog.")
    private = ROOT / ".env.supabase"
    if private.exists():
        values = dict(dotenv_values(private, interpolate=False))
    else:
        local = dotenv_values(ROOT / ".env", interpolate=False)
        runtime, reader = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
        values = {
            "DATABASE_URL": database_url("sai_runtime", runtime),
            "SQL_DATABASE_URL": database_url("sai_reader", reader),
            "RUNTIME_DATABASE_PASSWORD": runtime,
            "SQL_READER_PASSWORD": reader,
            "JWT_SECRET": secrets.token_urlsafe(48),
            "SEED_ADMIN_EMAIL": local.get("SEED_ADMIN_EMAIL", "admin@saitech.example"),
            "SEED_ADMIN_PASSWORD": secrets.token_urlsafe(24),
        }
        private.write_text("".join(f"{k}='{v}'\n" for k, v in values.items()), encoding="utf-8")
    os.environ.update(values)
    os.environ["PGSSLROOTCERT"] = str(ROOT / ".env.supabase-ca.crt")
    os.environ["DATABASE_URL"] = database_url(
        "postgres", (ROOT / ".env.supabase-password").read_text(encoding="utf-8-sig").strip()
    )
    from sqlalchemy import text

    from app.database.seed import main as seed
    from app.database.session import engine
    from app.database.setup_runtime import main as runtime_setup
    from app.database.setup_sql import main as reader_setup

    stage = "verify project schema"
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM public.alembic_version"))
            if revision != "0004":
                raise ValueError("Unexpected schema revision")
        stage = "SQL reader provisioning"
        await reader_setup()
        stage = "runtime provisioning"
        await runtime_setup()
        stage = "seed admin and synthetic documents"
        await seed()
        stage = "verify seed"
        async with engine.connect() as connection:
            counts = (
                (
                    await connection.execute(
                        text(
                            "SELECT (SELECT count(*) FROM users) AS users, "
                            "(SELECT count(*) FROM documents) AS documents, "
                            "(SELECT count(*) FROM employees) AS synthetic_employees"
                        )
                    )
                )
                .mappings()
                .one()
            )
            print(json.dumps(dict(counts)))
        print("Private runtime configuration saved in .env.supabase; secrets were not printed.")
    except Exception as exc:
        print(f"FAILED at {stage}: {type(exc).__name__}. No secret-bearing exception details logged.")
        raise SystemExit(1) from None
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
