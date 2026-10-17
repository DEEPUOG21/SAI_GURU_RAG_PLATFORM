import asyncio
from pathlib import Path

import asyncpg


async def main():
    url = Path(".local-database-url").read_text().replace("postgresql+asyncpg://", "postgresql://")
    connection = await asyncpg.connect(url)
    if not await connection.fetchval("SELECT 1 FROM pg_database WHERE datname='sai_guru_test'"):
        await connection.execute("CREATE DATABASE sai_guru_test")
    await connection.close()
    # This helper's URI has no query string (native Windows localhost test server).
    test_url = url.rsplit("/", 1)[0] + "/sai_guru_test"
    Path(".local-test-url").write_text(test_url.replace("postgresql://", "postgresql+asyncpg://"))
    print("Disposable sai_guru_test database is available.")


asyncio.run(main())
