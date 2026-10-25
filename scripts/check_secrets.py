"""Check that locally configured secrets were not copied into publishable project files."""
import os
from pathlib import Path

from dotenv import dotenv_values

secret_names = {"POSTGRES_PASSWORD", "SQL_READER_PASSWORD", "JWT_SECRET", "SEED_ADMIN_PASSWORD", "LLM_API_KEY", "INFERENCE_API_KEY", "LANGSMITH_API_KEY"}
values = [value for name, value in dotenv_values(".env").items() if name in secret_names and value and len(value) >= 12]
local_key = Path(".local-inference-key")
if local_key.exists():
    values.append(local_key.read_text().strip())
ignored = {".local", ".audit-tools", ".git", ".venv", "node_modules", ".model-cache", ".local-postgres", "dist", "test-results", "__pycache__", ".pytest_cache", ".ruff_cache", "sai_guru.egg-info"}
failures = []
checked = 0
for root, directories, files in os.walk("."):
    directories[:] = [name for name in directories if name not in ignored]
    for name in files:
        if (name.startswith(".env") and name != ".env.example") or name.startswith(".local-") or name.endswith((".pyc", ".log", ".tsbuildinfo")):
            continue
        path = Path(root) / name
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        checked += 1
        if any(value in content for value in values):
            failures.append(str(path))
if failures:
    raise SystemExit("Private configuration value found in: " + ", ".join(failures))
print(f"Checked {checked} publishable text files: no locally configured secrets found.")
