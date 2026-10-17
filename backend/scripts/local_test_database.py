"""Optional native PostgreSQL test helper. Install pgserver separately, never in production."""

import time
from pathlib import Path

import pgserver

directory = Path(".local-postgres").resolve()
server = pgserver.get_server(directory)
Path(".local-database-url").write_text(server.get_uri().replace("postgresql://", "postgresql+asyncpg://"))
print("Native test PostgreSQL started. Connection URL saved in ignored .local-database-url.", flush=True)
try:
    while True:
        time.sleep(1)
finally:
    server.cleanup()
