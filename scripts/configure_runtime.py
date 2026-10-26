"""Provision runtime credentials for the disposable native test database, without printing secrets."""

import asyncio
import os
import secrets
from pathlib import Path

from sqlalchemy.engine import make_url

os.environ["DATABASE_URL"] = Path(".local-test-url").read_text().strip()
key_file = Path(".local-runtime-password")
if not key_file.exists():
    key_file.write_text(secrets.token_urlsafe(48))
os.environ["RUNTIME_DATABASE_PASSWORD"] = key_file.read_text().strip()

from app.database.setup_runtime import main  # noqa: E402

asyncio.run(main())
Path(".local-runtime-url").write_text(
    make_url(os.environ["DATABASE_URL"])
    .set(username="sai_runtime", password=os.environ["RUNTIME_DATABASE_PASSWORD"])
    .render_as_string(hide_password=False)
)
