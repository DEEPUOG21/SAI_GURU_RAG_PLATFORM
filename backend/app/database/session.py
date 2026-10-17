from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session as SyncSession

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    get_settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=5, hide_parameters=True
)


class ScopedSession(AsyncSession):
    def __init__(self, *args, scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        if scope is not None:
            self.info.update(tenant_id=scope.tenant_id, user_id=scope.user_id)


@event.listens_for(SyncSession, "after_begin")
def transaction_scope(session, transaction, connection):
    if connection.dialect.name == "postgresql":
        for key in ("tenant_id", "user_id", "login_email"):
            connection.execute(
                text("SELECT set_config(:key, :value, true)"),
                {"key": "app." + key, "value": session.info.get(key, "")},
            )


async def bind_scope(db, **values):
    db.info.update(values)
    for key, value in values.items():
        await db.execute(text("SELECT set_config(:key, :value, true)"), {"key": "app." + key, "value": value})


Session = async_sessionmaker(engine, class_=ScopedSession, expire_on_commit=False)


async def require_runtime_role():
    async with engine.connect() as connection:
        unsafe = await connection.scalar(
            text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user")
        )
        owns_tables = await connection.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='documents' AND tableowner=current_user)"
            )
        )
        if unsafe or owns_tables:
            raise RuntimeError(
                "The service requires the non-owner sai_runtime database role. Run migrations and setup_runtime with separate owner credentials."
            )


async def get_db():
    async with Session() as db:
        yield db
