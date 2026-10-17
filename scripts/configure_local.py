"""Create a private local .env without printing secrets. Never overwrite existing configuration."""

import secrets
from pathlib import Path

target = Path(".env")
if target.exists():
    raise SystemExit(
        ".env already exists. Edit it explicitly; no values were overwritten."
    )
password, reader = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
values = {
    "POSTGRES_PASSWORD": password,
    "RUNTIME_DATABASE_PASSWORD": secrets.token_urlsafe(48),
    "SQL_READER_PASSWORD": reader,
    "DATABASE_URL": f"postgresql+asyncpg://sai:{password}@localhost:5432/sai_guru",
    "SQL_DATABASE_URL": f"postgresql+asyncpg://sai_reader:{reader}@localhost:5432/sai_guru",
    "JWT_SECRET": secrets.token_urlsafe(48),
    "SEED_ADMIN_PASSWORD": secrets.token_urlsafe(18),
}
lines = []
for line in Path(".env.example").read_text().splitlines():
    key = line.split("=", 1)[0]
    lines.append(f"{key}={values[key]}" if key in values else line)
target.write_text("\n".join(lines) + "\n")
print(
    "Created ignored .env with unique local credentials. Read SEED_ADMIN_PASSWORD there to sign in after seeding."
)
