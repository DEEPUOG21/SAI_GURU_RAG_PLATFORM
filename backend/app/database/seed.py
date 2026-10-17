import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.database.session import Session, engine
from app.models.entities import Tenant, User
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
    await engine.dispose()
    print("Admin account exists. Upload your knowledge documents through the UI.")


if __name__ == "__main__":
    asyncio.run(main())
