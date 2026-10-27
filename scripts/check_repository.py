"""Reject unwanted assistant artifacts and generated files in the source repository."""

import subprocess
from pathlib import Path, PurePosixPath

root = Path(__file__).resolve().parents[1]
blocked = {".claude", ".tokensave", "tokensave-docs", "claude.md"}
generated = {".local", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "dist"}
tracked = subprocess.check_output(
    ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root
).decode().split("\0")
failures = []
for filename in filter(None, tracked):
    if not (root / filename).exists():
        continue
    path = PurePosixPath(filename)
    if ({part.lower() for part in path.parts} & (blocked | generated)) or (
        path.name.startswith(".env") and path.name != ".env.template"
    ) or filename.startswith(("docs/audit/", "backend/scripts/")):
        failures.append(filename)
for path in root.iterdir():
    if path.name.lower() in blocked:
        failures.append(f"{path.name} (unwanted local artifact)")
if failures:
    raise SystemExit("Repository cleanup required:\n" + "\n".join(sorted(set(failures))))
print("Repository layout check passed: no unwanted assistant artifacts or tracked runtime files.")
