# Development

Run commands from the repository root unless they explicitly change directory.

## Docker Compose

Install Python 3.11+, Node 22+ and Docker Compose:

```sh
python scripts/configure_local.py
docker compose up --build
```

The setup script refuses to overwrite `.env`. Use `.env.template` when editing existing configuration. Compose starts PostgreSQL, migrates the schema, provisions restricted runtime and SQL-reader roles, seeds the admin account and starts the API and frontend. Sign in using the seed credentials in `.env`.

For Ollama, pull the configured model on the host and make it reachable from the backend container. Compose uses `http://host.docker.internal:11434/v1`. Set `GENERATION_MODE=extractive` for quoted search without generation. Hosted model configuration is in [deployment](deployment.md).

Upload and process the documents in `data/demo/` through Knowledge Library. See [data configuration](../data/README.md) for the approved benchmark and private overrides.

## Separate processes

```sh
python -m venv .venv
# Activate .venv with your shell's activation command.
python -m pip install -r backend/requirements.lock
python -m pip install -e './backend[dev,local]'
alembic -c backend/alembic.ini upgrade head
```

Use owner credentials only while migrating and provisioning. Run `python -m app.database.setup_sql` and `python -m app.database.setup_runtime` with provisioning configuration, then set the API's `DATABASE_URL` to the restricted runtime role. `SQL_DATABASE_URL` uses the reader role. Start the API with `uvicorn app.main:app --host 127.0.0.1 --port 8000`.

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Set `VITE_API_URL` before starting Vite if the API is not at `http://localhost:8000`. Add the frontend's exact origin to `CORS_ORIGINS`.

The optional authenticated CPU service is documented in [inference](../inference/README.md). `python scripts/run_local_inference.py` reuses the private local key and model cache.

## Tests

```sh
python scripts/check_repository.py
python scripts/check_secrets.py
python -m ruff check backend
python -m pytest backend/tests -q
cd frontend
npm test
npm run lint
npm run build
```

Browser tests live in `frontend/e2e/`; run them with its configured Playwright environment. Their fixtures are isolated from production.

Three backend database integration tests are skipped unless `SAI_INTEGRATION=1`. Use a migrated disposable `sai_guru_test` database, provision its runtime role and set `TEST_RUNTIME_DATABASE_URL`. Never run them against production.

On Windows without Docker, the optional development package `pgserver` can provide a loopback-only PostgreSQL instance. Run `python scripts/local_test_database.py` and keep it running. In another terminal run `python scripts/prepare_test_database.py`, load the private `.local-test-url` into `DATABASE_URL`, migrate, then run `python scripts/configure_runtime.py`. It saves the restricted URL to `.local-runtime-url`; use it as `TEST_RUNTIME_DATABASE_URL` and set `SAI_INTEGRATION=1` for pytest.

## Maintenance

Keep application code in its service folder, reusable commands in `scripts/`, and maintained documentation in `docs/`. Raw scans and temporary diagnostics belong in ignored `.local/`. Preserve active environments, databases and model caches; do not commit private configuration or generated output.
