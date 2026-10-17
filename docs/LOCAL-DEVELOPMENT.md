# Local development

Run commands from the repository root unless a step explicitly says otherwise. Do not use a production database for tests.

## Compose

```sh
python scripts/configure_local.py
docker compose up --build
docker compose logs -f backend worker
```

`docker compose down` stops containers and preserves the named PostgreSQL volume. Do not add `--volumes` unless you deliberately want to destroy local data. Uploaded bytes, document versions, jobs, queries and evaluations all live in PostgreSQL. Model caches may disappear and can be downloaded again.

## Run components separately

Start only the local database:

```sh
docker compose up -d db
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```sh
# macOS / Linux
source .venv/bin/activate
```

Then install and prepare the backend:

```sh
python -m pip install -r backend/requirements.lock
python -m pip install -e './backend[dev,local]'
python -m alembic -c backend/alembic.ini upgrade head
python -m app.database.setup_sql
python -m app.database.setup_runtime
python -m app.database.seed
```

Use the migration-owner URL for the setup commands above. Set a private `RUNTIME_DATABASE_PASSWORD` of 32–128 random URL-safe characters before provisioning. Before starting the API, change `DATABASE_URL` to the same database using `sai_runtime` and that password; owner credentials are rejected at startup.

```sh
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

For an optional worker, use the runtime database URL and set `WORKER_TENANT_ID` to the tenant UUID in a second activated terminal, then run `python -m app.ingestion.worker`. The worker polls that tenant's jobs, acquires a document advisory lock, records processing stages and indexes the file. A killed process releases its connection lock; a later worker can resume the unfinished job. You can instead press **Process** beside an uploaded document, which holds an authenticated HTTP request while processing.

In a third terminal:

```sh
cd frontend
npm ci
npm run dev
```

Create `frontend/.env.local` containing `VITE_API_URL=http://localhost:8000` if the default needs changing. Restart Vite after environment changes. The frontend has no database credentials or LLM keys.

## Local LLM choices

### Ollama

Install Ollama separately, then run:

```sh
ollama pull qwen2.5:3b
ollama serve
```

If the desktop app already serves Ollama, a second `serve` may report that the port is in use; use the running instance. Separate Python development uses `LLM_URL=http://localhost:11434/v1`. Compose overrides it with `http://host.docker.internal:11434/v1`. A service bound only to localhost may not accept container connections: configure Ollama's host setting for the Docker-accessible interface and restrict network exposure with your firewall, or run the Python backend directly. Never expose an unauthenticated model endpoint publicly.

### Included CPU model service

The optional service runs embeddings, reranking and a small GGUF LLM. Its model key is required. Install the CPU wheel from the runtime maintainer's wheel index:

```sh
python -m pip install -r inference/requirements.txt --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --only-binary llama-cpp-python
python scripts/run_local_inference.py
```

The helper generates an ignored `.local-inference-key`, downloads Qwen2.5-3B-Instruct Q4_K_M (about 2.1 GB) and serves port 7860 using four CPU threads. Configure `LLM_URL=http://localhost:7860/v1`, `LLM_MODEL=sai-local`, and set `LLM_API_KEY` to the private key file's contents. Optionally use HTTP embedding/reranking endpoints on that service as documented in SETUP. The small model is a resource-conscious demonstration, not a high-quality verifier. The service can be run with a different compatible model via `MODEL_PATH` or `MODEL_REPO`/`MODEL_FILE`. Model weights use the upstream Qwen Research license, separately from the app's MIT license; see `inference/README.md`.

## Migrations and seeding

`python -m alembic -c backend/alembic.ini upgrade head` is safe to repeat. The first migration is frozen SQL, not runtime `create_all`. The second removes broad table privileges, including Supabase anonymous/authenticated API access. Use a dedicated database/project for this application. Do not regenerate `0001_initial.sql` after deployment; create a new migration for schema changes. Destructive downgrades are intentionally unavailable; restore a tested backup instead.

Seeding uses eight realistic but fictional documents and eight fixed synthetic employee records dated in 2026. Repeated seeding is incremental and does not reset passwords. Uploaded files with unchanged hashes and access rules retain their version; changed content receives a new version and only that document is reindexed.

## Tests

```sh
python -m ruff check backend
python -m pytest backend/tests -q
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
npx playwright test
```

The ordinary backend suite skips one database integration scenario unless `SAI_INTEGRATION=1`. Browser tests use Chrome locally; CI installs Playwright Chromium. Browser fixtures are isolated test responses, never production mock data.

For real integration, create a disposable **sai_guru_test** database with pgvector available. Set `DATABASE_URL` to it, run migrations, set `SAI_INTEGRATION=1`, and run pytest. The test refuses any other database name. It performs real model inference, verifies tenant/RBAC isolation, hashes/versions, retrieval scores, SSE responses, feedback and deletion. It cleans up its own test tenants after success; a failed run can leave diagnostic test rows.

On Windows without Docker, an optional development-only helper was used for verification:

```sh
python -m pip install pgserver
python backend/scripts/local_test_database.py
```

Keep that terminal running; from another root terminal run `python backend/scripts/prepare_test_database.py`. Read the ignored `.local-test-url` into `DATABASE_URL`, migrate it, and run the integration test. This is native PostgreSQL bundled for testing, not a deployment dependency. Its local trust-auth configuration must never be exposed beyond loopback.

After preparing that test database and starting the included inference service, `python backend/scripts/system_smoke.py` exercises actual HTTP model inference, SQL privilege denials, seeded ingestion, LLM streaming and the evaluation endpoint. It writes measured synthetic results to `docs/local-verification.json`. That command does not publish or send real company data.

With the local preview API running, `python backend/scripts/conversation_smoke.py` checks real multi-turn general questions, pronoun resolution, cited policy follow-ups, a topic switch, labeled missing-evidence guidance, and reloaded message labels. It uses credentials from the ignored `.env` without printing them.
