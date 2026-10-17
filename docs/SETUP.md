# Setup

Sai Guru has three required application components: a browser frontend, a Python API, and PostgreSQL with pgvector. Models can run locally or in the included private inference service. Redis is unnecessary.

## Prerequisites

- Python 3.11 or newer; the verified development interpreter was Python 3.11.
- Node 22 or newer and npm. Use `frontend/package-lock.json` with `npm ci`.
- Docker Desktop (Windows/macOS) or Docker Engine + Compose (Linux) for the simplest database setup.
- Internet access for Python/Node dependencies and the initial model downloads.
- Several GB of free disk and RAM for local generation; model caches are disposable. The default embedding and reranking models use ONNX CPU inference.

Run `python --version`, `node --version`, and `docker compose version`. Start Docker Desktop before Compose commands. On Windows, a Docker installation may require virtualization/WSL setup and a reboot; installing the application itself does not perform these system changes.

## Environment configuration

From the repository root run `python scripts/configure_local.py`. This creates `.env` only if it does not exist. It generates database, SQL-reader, signing and admin passwords without printing them. Open the file locally to retrieve your admin password. Never paste it into a public issue. `.gitignore` and `.dockerignore` exclude private configuration.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy async PostgreSQL URL: use `sai_runtime` for API/workers and an owner only for migrations/setup. Example shape: `postgresql+asyncpg://USER:PASSWORD@HOST:5432/DATABASE`. Percent-encode password punctuation. |
| `RUNTIME_DATABASE_PASSWORD` | Private 32?128 character URL-safe password for `sai_runtime`. |
| `WORKER_TENANT_ID` | Tenant UUID required by the optional worker; enable Compose profile `worker`. |
| `POSTGRES_PASSWORD` | Compose's local PostgreSQL password; generated URL-safe by the setup script. |
| `SQL_READER_PASSWORD` | Password for the separately provisioned `sai_reader` role. Use 24–128 random letters/digits/underscore/hyphen. |
| `SQL_DATABASE_URL` | Same database, restricted SQL-reader credentials. Must differ from `DATABASE_URL`. |
| `JWT_SECRET` | Random signing secret, at least 32 characters. Authentication fails closed if absent. |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` | Create the initial SaiTech admin; minimum password length 12. Rerunning the seed does not reset an existing password. |
| `CORS_ORIGINS` | Comma-separated exact frontend origins, without trailing slash. Example: `http://localhost:5173,https://your-app.vercel.app`. |
| `VITE_API_URL` | Browser-visible API origin, without `/api/v1`. Set at frontend build time. It is the only frontend environment setting. |
| `EMBEDDING_PROVIDER` | `local` (default) or `http`. |
| `EMBEDDING_MODEL` | Default `BAAI/bge-small-en-v1.5`. The schema requires 384 dimensions. |
| `EMBEDDING_URL` | Full embedding endpoint for HTTP mode, e.g. `https://your-space.hf.space/embeddings`. |
| `RERANKER_PROVIDER` | `local` (default) or `http`. |
| `RERANKER_MODEL` | Default `Xenova/ms-marco-MiniLM-L-6-v2`. |
| `RERANKER_URL` | Full HTTP reranking endpoint. |
| `INFERENCE_API_KEY` | Private key for the optional model host; sent server-to-server. |
| `LLM_URL` | Compatible API base ending in `/v1`. Default: local Ollama. |
| `LLM_MODEL` | Model name recognized by that provider. Included inference service uses `sai-local`. |
| `LLM_API_KEY` | Optional provider key; use the inference key for the included model host. Never expose it to React. |
| `GENERATION_MODE` | `llm` or explicitly labeled `extractive`. No silent fake response fallback. |
| `GROUNDING_ACTION` | One controlled `regenerate` attempt (default), or `refuse`. |
| `GENERAL_FALLBACK_ENABLED` | `true` (default) allows clearly labeled general guidance when company evidence is missing; `false` keeps strict abstention. |
| `QUERY_TIMEOUT_SECONDS` | Overall query limit, default 120, allowed 10–600. Cold CPU models may need 300. |
| `MAX_UPLOAD_MB` | Default 10; parser limits also cap expanded DOCX, PDF pages, extracted text and chunk count. |
| `RATE_LIMIT_PER_MINUTE` | Per-user query budget, default 30. Login/upload/evaluation have separate budgets. |
| `LLM_INPUT_COST_PER_MILLION` / `LLM_OUTPUT_COST_PER_MILLION` | USD rates used only with reported token counts. Zero for local inference; configure actual rates for a metered provider. |
| `PORT` | API listen port in Docker. Render supplies it. |

The backend reads `.env` relative to the process working directory. All documented Python commands run from the repository root. The frontend reads `frontend/.env.local` during separate Vite development, or hosting variables during deployment; root `.env` is passed by Compose for its build argument.

## Local first run

Run `docker compose up --build`. The one-shot `migrate` service waits for the database, runs all migrations, sets up restricted runtime and SQL-reader roles and seeds the synthetic dataset. Process queued documents using the UI. An optional tenant-scoped worker can be enabled with the `worker` Compose profile; models download on first use.

Open http://localhost:5173 and sign in with the `.env` admin credentials. Real query generation additionally needs Ollama or the model service; see the next guide. To explore document search without generation, select `GENERATION_MODE=extractive` and run `docker compose up -d --force-recreate backend`.

## Adding accounts

There is no public registration endpoint. Sign in as ADMIN, open http://localhost:8000/docs, authorize using the bearer token from `/api/v1/auth/login`, and call `POST /api/v1/auth/users` with an email, a unique password of at least 12 characters, and ADMIN/MANAGER/EMPLOYEE. Accounts are created in the signed-in admin's tenant. MANAGER can manage documents/evaluations, EMPLOYEE can only query accessible content. User creation currently uses the API; there is no account-management UI.
