# Project workspace rules

- Keep application code in `backend/`, `frontend/`, and `inference/`; operational scripts in `scripts/`; documentation in `docs/`.
- Put private deployment records, temporary diagnostics, downloaded audit tools, and archives under ignored `.local/`.
- Do not create or restore `.claude/`, `.tokensave/`, `tokensave-docs/`, `CLAUDE.md`, or Headroom/TokenSave hooks and integrations in this project. The user explicitly opted out of them.
- Preserve the workspace settings that disable those automatic integrations. Do not enable them to perform a task.
- Keep credentials and runtime databases private. Do not move or delete active databases, environments, or model caches merely to tidy the source tree.
- Retain `.env.example` as the required configuration template. Keep the user-approved synthetic knowledge documents together in `data/demo/`. Do not add example evaluation datasets unless requested.
- Before committing, run `python scripts/check_repository.py` and check that generated files and secrets are not staged.
