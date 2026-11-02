from functools import lru_cache

import sqlglot
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

SQL_TEMPLATES = {
    "last_month": "SELECT COUNT(*) AS employee_count FROM employee_analytics WHERE joined_at >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' AND joined_at < DATE_TRUNC('month', CURRENT_DATE) LIMIT 100",
    "departments": "SELECT department, COUNT(*) AS employee_count FROM employee_analytics GROUP BY department ORDER BY department LIMIT 100",
    "growth": "SELECT DATE_TRUNC('month', joined_at) AS month, COUNT(*) AS employees_joined FROM employee_analytics GROUP BY DATE_TRUNC('month', joined_at) ORDER BY month DESC LIMIT 100",
    "count": "SELECT COUNT(*) AS employee_count FROM employee_analytics LIMIT 100",
}


def normalize(sql):
    statements = sqlglot.parse(sql, read="postgres")
    if len(statements) != 1 or statements[0] is None:
        raise ValueError("Exactly one SELECT is required.")
    return statements[0].sql(dialect="postgres")


def validate_sql(sql):
    normalized = normalize(sql)
    if normalized not in {normalize(value) for value in SQL_TEMPLATES.values()}:
        raise ValueError("SQL is outside the audited, read-only template allowlist.")
    return normalized


def generate_sql(question):
    question = question.lower()
    if "last month" in question and ("joined" in question or "hired" in question):
        return SQL_TEMPLATES["last_month"]
    if "department" in question:
        return SQL_TEMPLATES["departments"]
    if "growth" in question or "monthly" in question:
        return SQL_TEMPLATES["growth"]
    if "how many employees" in question or "headcount" in question:
        return SQL_TEMPLATES["count"]
    raise ValueError(
        "SQL currently supports headcount, joins last month, department counts and monthly joins only."
    )


@lru_cache
def sql_engine():
    url = get_settings().sql_database_url
    if not url or url == get_settings().database_url:
        raise ValueError("SQL route requires a separate read-only SQL_DATABASE_URL.")
    return create_async_engine(url, pool_size=2, max_overflow=0, pool_pre_ping=True, hide_parameters=True)


async def run_sql(question, scope):
    if scope.level < 1:
        raise PermissionError("Employee analytics requires MANAGER or ADMIN.")
    async with sql_engine().connect() as connection:
        async with connection.begin():
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            await connection.execute(text("SET LOCAL statement_timeout = '3000ms'"))
            await connection.execute(
                text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": scope.tenant_id}
            )
            role = (
                await connection.execute(
                    text(
                        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls FROM pg_roles WHERE rolname = CURRENT_USER"
                    )
                )
            ).one()
            if any(role):
                raise PermissionError("SQL database user has unsafe administrative privileges.")
            columns = (
                (
                    await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = 'employee_analytics'"
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not {"department", "joined_at"} <= set(columns):
                raise ValueError("Read-only analytics view is missing. Run SQL role setup.")
            sql = validate_sql(generate_sql(question))
            result = await connection.execute(text(sql))
            result_columns = list(result.keys())
            rows = result.mappings().fetchmany(100)
            return {
                "sql": sql,
                "columns": result_columns,
                "rows": [
                    {
                        key: value.isoformat() if hasattr(value, "isoformat") else value
                        for key, value in row.items()
                    }
                    for row in rows
                ],
            }
