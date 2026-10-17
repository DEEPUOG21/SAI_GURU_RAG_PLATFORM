"""Inspect only the synthetic demo's raw model draft while diagnosing generation."""

import asyncio

import system_smoke  # Configure the local disposable database and inference provider.
from sqlalchemy import select

from app.agents.workflow import execute
from app.database.session import Session, engine
from app.models.entities import User
from app.security.scope import Scope


async def main():
    parts = []

    async def emit(event, data):
        if event == "draft":
            parts.append(data["text"])

    async with Session() as db:
        user = await db.scalar(select(User).where(User.email == system_smoke.get_settings().seed_admin_email))
        result = await execute(
            db,
            Scope(user.tenant_id, user.id, user.role),
            "How many paid annual leave days do full-time SaiTech employees receive?",
            [],
            emit,
        )
    print({"draft": "".join(parts), "final": result["answer"], "trace": result["trace"]})
    await engine.dispose()


asyncio.run(main())
