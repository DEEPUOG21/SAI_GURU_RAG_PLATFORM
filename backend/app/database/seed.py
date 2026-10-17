import asyncio
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import get_settings
from app.database.session import Session, engine
from app.ingestion.service import upload
from app.models.entities import Document, Employee, Tenant, User
from app.security.auth import passwords


async def main():
    cfg = get_settings()
    if len(cfg.seed_admin_password) < 12:
        raise ValueError("Set SEED_ADMIN_PASSWORD to a unique password of at least 12 characters.")
    async with Session() as db:
        user = await db.scalar(select(User).where(User.email == cfg.seed_admin_email.lower()))
        if user:
            tenant = await db.get(Tenant, user.tenant_id)
            if user.role != "ADMIN" or tenant.name != "SaiTech":
                raise ValueError("Seed email belongs to another workspace or a non-admin account.")
        else:
            tenant = Tenant(name="SaiTech")
            db.add(tenant)
            await db.flush()
            db.add(
                User(
                    tenant_id=tenant.id,
                    email=cfg.seed_admin_email.lower(),
                    role="ADMIN",
                    password_hash=await asyncio.to_thread(passwords.hash, cfg.seed_admin_password),
                )
            )
            await db.commit()
        for path in sorted((Path(__file__).resolve().parents[3] / "data" / "demo").glob("*.md")):
            existing = await db.scalar(
                select(Document).where(Document.tenant_id == tenant.id, Document.name == path.name)
            )
            if existing and existing.status not in {"COMPLETED", "FAILED"}:
                continue
            await upload(db, tenant.id, path.name, path.read_bytes())
        count = await db.scalar(
            select(func.count()).select_from(Employee).where(Employee.tenant_id == tenant.id)
        )
        if not count:
            # Fixed, explicitly synthetic records. Results change with calendar-based queries, not invented metrics.
            for department, month in [
                ("Engineering", 1),
                ("Engineering", 2),
                ("Product", 3),
                ("People", 4),
                ("Engineering", 6),
                ("Support", 8),
                ("Security", 8),
                ("Engineering", 9),
            ]:
                db.add(
                    Employee(
                        tenant_id=tenant.id,
                        department=department,
                        joined_at=datetime(2026, month, 5, tzinfo=timezone.utc),
                    )
                )
            await db.commit()
    await engine.dispose()
    print(
        "SaiTech synthetic documents queued; admin account exists. Start the worker or select Process in the UI."
    )


if __name__ == "__main__":
    asyncio.run(main())
