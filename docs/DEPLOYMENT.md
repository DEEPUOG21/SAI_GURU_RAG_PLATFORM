# Free deployment: GitHub, Supabase, Render and Vercel

This guide deploys a **personal portfolio demo** with no mandatory paid service. It uses Vercel Hobby for React, Render Free for FastAPI, Supabase Free for PostgreSQL/pgvector, and an optional free Hugging Face CPU Space for inference. The extra model host is necessary for a realistic free CPU design: do not expect a 512 MB API container to run embeddings, a reranker and a generative model together.

The instructions match this repository. Cloud deployment has not been performed on your accounts. Interface labels, available plans and limits can change; check the linked official pages before selecting resources. Account approval, regional availability and free quotas are controlled by the providers.

See [current hardening results and release blockers](HARDENING-RESULTS.md) before release. Use your existing dedicated projects; creating replacements is unnecessary.

## 1. Understand the cost boundaries

| Component | Select | Avoid for a ₹0 demo |
|---|---|---|
| Frontend | Vercel Hobby, personal non-commercial project | Pro trials/upgrades, paid team features, purchased domain |
| Backend | Render Web Service, **Free** instance | Paid instance size, persistent disk, paid background worker, paid cron |
| Database | Supabase organization/project on **Free** | Pro organization, paid compute, custom domain, point-in-time recovery |
| Inference | Hugging Face Docker Space on **CPU Basic / Free** | Upgraded CPU, GPU, paid Inference Endpoints or metered providers |
| Repository | GitHub personal repository | Paid Actions overages beyond your account's included allowance |

Render's documented free web instance has 512 MB RAM and can sleep after 15 minutes without traffic; its filesystem is ephemeral. This app therefore persists files/jobs in PostgreSQL and offers request-driven document processing instead of requiring a paid worker. [Render free services](https://render.com/docs/free), [compute plans](https://render.com/docs/compute-plans).

Supabase currently documents 500 MB of database storage on Free and pausing after a week of inactivity. This application stores original file bytes, versions, vectors and query traces there, so keep the portfolio corpus small and remove obsolete documents. [Supabase pricing](https://supabase.com/pricing), [project pausing](https://supabase.com/docs/guides/platform/free-project-pausing).

Vercel Hobby is for personal, non-commercial use. A real employer deployment requires reassessing both hosting terms and operational requirements. [Vercel Hobby plan](https://vercel.com/docs/plans/hobby).

Free Spaces can sleep and have limited CPU; select free hardware explicitly and never attach paid upgrades as a troubleshooting shortcut. [Spaces overview](https://huggingface.co/docs/hub/spaces-overview), [hardware and sleep behavior](https://huggingface.co/docs/hub/spaces-gpus).

## 2. Prepare and publish the GitHub repository

1. Create or sign in to your GitHub account.
2. Create a new repository named `sai-guru`. A public repository is convenient for a portfolio. Do not initialize it with another README if you will push these existing files.
3. In this project's root, verify `.gitignore` exists. It excludes `.env`, local database files, credentials, virtual environments, node_modules and model caches.
4. Run local checks from `LOCAL-DEVELOPMENT.md`. Do not publish test credentials, actual company documents, model weights or local database files.
5. Initialize and inspect Git:

```sh
git init
git branch -M main
git add .
git status --short
git diff --cached --stat
```

6. Review the staged file list. `.env.example` is expected; `.env`, `.local-inference-key`, `.local-postgres`, `.venv` and `.model-cache` must not be present. `docs/local-verification.json` contains synthetic measured results, not live customer data.
7. Commit and push, replacing the remote with your repository:

```sh
git commit -m "Build Sai Guru knowledge intelligence platform"
git remote add origin https://github.com/YOUR-USERNAME/sai-guru.git
git push -u origin main
```

Authenticate with GitHub's normal credential manager/browser flow. Do not embed an access token in the remote URL. The included workflow validates pull requests and pushes to main; it does not deploy until explicitly configured below.

## 3. Create a dedicated Supabase project

1. Create a Supabase account and an organization on the Free plan.
2. Create a **new dedicated project**, for example `sai-guru`. Do not point migrations at an unrelated project's public schema: migration 0002 revokes broad table access in that schema.
3. Choose a region near the intended Render region. Generate and store a strong database password. Wait for project provisioning.
4. Open **Connect** and select a direct PostgreSQL connection if your machine supports the required networking, or the **session pooler** for IPv4-compatible persistent connections.
5. Copy the host, database, port, username and password. The pooler username often includes the project reference; copy the displayed value exactly. Use session mode on port 5432, not transaction mode on 6543. The worker relies on session advisory locks, and migrations need predictable sessions. [Supabase connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres).
6. In the project's SQL editor enable the extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
```

If `vector` already exists in the `extensions` schema, ensure your database role's `search_path` includes that schema before migrating. A brand-new dedicated project with the extension in public is the simplest setup. [Supabase vector columns](https://supabase.com/docs/guides/ai/vector-columns).

### Configure a local migration connection

Edit your private root `.env` and set `DATABASE_URL` to this shape:

```text
DATABASE_URL=postgresql+asyncpg://YOUR_POOLER_USERNAME:ENCODED_PASSWORD@YOUR_POOLER_HOST:5432/postgres?ssl=require
```

Use your actual values. URL-encode punctuation in the password, particularly `@`, `:`, `/`, `?`, `#` and `%`; use a local editor or Python's URL-quoting utility without logging the password. Do not use a website to encode credentials. For stronger certificate verification, configure `ssl=verify-full` with the appropriate trusted CA for your connection.

Activate the Python environment and run from the root:

```sh
python -m pip install -r backend/requirements.lock
python -m pip install -e './backend[dev,local]'
python -m alembic -c backend/alembic.ini upgrade head
python -m app.database.setup_sql
python -m app.database.setup_runtime
python -m app.database.seed
```

Setup requires the private `SQL_READER_PASSWORD` and a 32?128 character URL-safe `RUNTIME_DATABASE_PASSWORD`. The seed requires your `SEED_ADMIN_PASSWORD`. It creates SaiTech, the admin, eight synthetic employee records and eight queued documents. It does not need a running LLM.

In the SQL editor confirm:

```sql
SELECT version_num FROM alembic_version;
SELECT extversion FROM pg_extension WHERE extname = 'vector';
SELECT name, status, version FROM documents;
```

The migration version should be `0004`. Documents initially show UPLOADED. Keep migrations outside API startup: run them deliberately before deploying schema-dependent code.

### Restricted runtime credentials

Use `sai_runtime` and its private password for the API and workers after owner-only migrations/setup. For a session pooler, verify its custom-role username format (for example `sai_runtime.PROJECT_REF`). The API and worker reject owner/superuser/bypass-RLS connections at startup. Never supply the migration-owner password to the deployed API.

### Restricted SQL credentials

`app.database.setup_sql` creates `sai_reader`, grants only the tenant-filtered `employee_analytics` view and enables default read-only transactions. Configure `SQL_DATABASE_URL` using this role and the same database. For a Supabase session pooler, use the role/project-reference username format required by that pooler, such as `sai_reader.PROJECT_REF`; verify the exact connection against the provider's current instructions.

Test this connection before enabling the SQL route. It must be able to query the view after setting `app.tenant_id`, but it must not read `users` or modify `employees`. The API rejects a missing/shared connection and administrative roles. If the reader connection is not ready, leave it unset: document RAG continues to work and analytics requests fail explicitly.

The browser never uses Supabase credentials or its direct table API. Migration 0002 revokes table grants from PUBLIC, `anon` and `authenticated`, where those roles exist. Restricted runtime credentials belong only in private server configuration; keep owner credentials in the migration environment.

## 4. Host inference on a free CPU Space

You can skip this step if you already have an authorized, reachable embedding/reranker/LLM host. A publicly deployed Render service cannot reach `localhost` on your laptop. Do not make a paid LLM key mandatory.

1. Create a Hugging Face account and a new **Docker Space**.
2. Select **CPU Basic / Free** hardware. A public Space repository is acceptable for this synthetic demo because requests still require the application key; never commit private documents or secrets to it.
3. Upload these repository files to the Space, preserving paths:
   - `inference/server.py`
   - `inference/requirements.txt`
   - `inference/Dockerfile`
4. Copy `inference/Dockerfile` to a file named `Dockerfile` at the **Space root**. The COPY instructions reference the retained `inference/` folder.
5. Copy `inference/README.md` to the Space root `README.md`. Its front matter selects Docker and port 7860.
6. Under Space **Settings → Variables and secrets**, add a secret named `INFERENCE_API_KEY` with at least 32 random characters. Generate it locally; reuse that exact value only in Render's private model settings.
7. Keep the included Qwen2.5-3B-Instruct quantized model initially. Its weights are approximately 2.1 GB and use the upstream Qwen Research license (separate from the application's MIT license; linked in `inference/README.md`). Model downloads occur at startup; wait for the build and initial download. Optional variables `MODEL_REPO` and `MODEL_FILE` select a compatible GGUF; changing them changes resource needs and output quality.
8. Copy the actual `.hf.space` application origin from the running Space. Do not use the repository page URL as an API URL.
9. Verify a request without a key is rejected. An authenticated POST to `/embeddings` with `{"input":["SaiTech leave policy"],"model":"BAAI/bge-small-en-v1.5"}` should return a 384-dimensional vector. `/rerank` accepts `query` and `documents`; `/v1/chat/completions` serves streamed generation with model alias `sai-local`.

The service is stateless and retains only disposable model caches. Public demo data sent for inference is processed by the Space; tenant filtering happens in FastAPI before text is sent. Do not use real confidential data on a free demo host without an appropriate privacy/security review. The small CPU model is imperfect: use the evaluation dashboard and inspect its sources rather than assuming every grounding verdict is correct.

If free hardware is unavailable, you can still run all components locally at no service charge. There is no guarantee of perpetual zero-cost cloud capacity. Do not silently switch to billable hardware or an external metered inference provider.

## 5. Deploy the FastAPI backend on Render

1. Sign in to Render and connect the GitHub account containing `sai-guru`.
2. Select **New → Web Service** and choose this repository. Grant access only to the repository needed.
3. Select the Docker runtime, branch `main`, and the **Free** instance.
4. Keep the repository root as the Docker context. Set Dockerfile path to `backend/Dockerfile`.
5. Do not create a paid worker or persistent disk. Uploaded files and job state live in Supabase; use the UI Process button on this free path.
6. Add private environment variables:

```text
DATABASE_URL=<your tested sai_runtime Supabase SQLAlchemy async URL>
SQL_DATABASE_URL=<your tested restricted reader URL, optional until configured>
JWT_SECRET=<a new random value of at least 32 characters>
CORS_ORIGINS=https://YOUR-FRONTEND.vercel.app
EMBEDDING_PROVIDER=http
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_URL=https://YOUR-SPACE.hf.space/embeddings
RERANKER_PROVIDER=http
RERANKER_URL=https://YOUR-SPACE.hf.space/rerank
INFERENCE_API_KEY=<the Space secret>
LLM_URL=https://YOUR-SPACE.hf.space/v1
LLM_MODEL=sai-local
LLM_API_KEY=<the Space secret>
GENERATION_MODE=llm
GROUNDING_ACTION=regenerate
GENERAL_FALLBACK_ENABLED=true
QUERY_TIMEOUT_SECONDS=300
LLM_INPUT_COST_PER_MILLION=0
LLM_OUTPUT_COST_PER_MILLION=0
```

Keep secrets out of screenshots. No frontend variable should contain a signing key, SQL URL or model key. Render supplies `PORT`; the Docker command respects it. The backend does not require cloud-specific code or Cloud Run.

7. Set the health-check path to `/api/v1/health`. Liveness does not depend on the sleeping model host. Set **Auto-Deploy off** if you intend to use the post-CI deploy hook described below; avoid deploying before tests finish.
8. Deploy and inspect logs for successful startup and the assigned port. A running `/health` with a failing `/ready` usually means database credentials, TLS or migrations need attention.
9. Open `https://YOUR-API.onrender.com/api/v1/health`, then `/api/v1/ready`, then `/docs`. Expect JSON status responses and OpenAPI documentation. Readiness checks the database, extension and schema version; model requests are checked on use.

The included `render.yaml` is an alternative Blueprint. It defaults to **extractive mode** so a newly provisioned app never implies that an LLM is already configured. Add the LLM settings above and switch to `llm` for generated answers. The embedding/reranking model host is still required to process and rank documents.

## 6. Deploy React on Vercel

1. Sign in to Vercel on the Hobby plan for this personal portfolio.
2. Select **Add New → Project**, import the GitHub repository and grant it access.
3. Set **Root Directory** to `frontend` and select Vite.
4. Use install command `npm ci`, build command `npm run build`, and output directory `dist`.
5. Add one environment variable: `VITE_API_URL=https://YOUR-API.onrender.com`. Do not append `/api/v1` and do not enter a model or database secret.
6. Deploy. Vite replaces `VITE_*` values at build time; changing them requires redeployment. [Vercel's Vite guide](https://vercel.com/docs/frameworks/frontend/vite).
7. Copy the production frontend origin and update Render's `CORS_ORIGINS` to match it exactly. For multiple explicitly allowed origins, separate them with commas and no surrounding spaces.
8. If the Vercel URL changed after deployment, redeploy/restart the backend after updating CORS. The included `vercel.json` provides SPA fallback and basic security headers.

Do not automatically allow every preview-domain wildcard in CORS. Add a specific preview origin when needed, then remove it afterward. An `http://` backend behind an `https://` frontend will be blocked as mixed content; use both providers' HTTPS origins.

## 7. Verify the integrated application

1. Open Vercel. The status should eventually say **Database connected**. A first request can wake Render and take longer than a warm request.
2. Sign in with the admin account seeded into **that Supabase database**. A local Docker admin is a different account/database.
3. Open Knowledge Library. Check all eight seeded documents. Press **Process** for each UPLOADED document; keep the request open. If a cold provider causes failure, wake/check the Space and retry FAILED documents.
4. Confirm each indexed document shows COMPLETED and a detail preview contains actual text/section metadata.
5. Ask about annual leave. Watch provisional tokens. Confirm that an accepted answer has real source cards, or an explicit insufficient-evidence response when verification fails.
6. Open the source card. Confirm the text actually supports the claim.
7. Select Inspect retrieval. Confirm real dense/lexical/RRF/reranker scores and grounding information. Missing provider scores must show unavailable/degraded, not invented values.
8. Run evaluation and wait. Read the real results and methodology, including the lexical and label-based proxy metrics.
9. Create an EMPLOYEE through the admin API and verify that uploading, deletion and evaluations are denied. Create another tenant only through a controlled admin/database provisioning process; public tenant registration is not implemented.
10. Delete a test document. Confirm its chunks disappear from search and old history warns when cited sources are no longer accessible.

## 8. CI and deployment automation

`.github/workflows/ci.yml` validates frontend lint/types/tests/build/browser behavior, backend lint/unit/API/security/integration tests against pgvector PostgreSQL, and both application Docker builds.

For the optional post-CI Render deploy hook:

1. In Render service settings copy its private deploy-hook URL.
2. In GitHub repository **Settings → Secrets and variables → Actions**, create secret `RENDER_DEPLOY_HOOK` with that URL.
3. Create repository variable `ENABLE_DEPLOYMENT=true` only when you want main-branch pushes to deploy after checks pass.
4. Configure the GitHub `production` environment and any review restrictions you want.
5. Disable Render's independent auto-deploy to avoid bypassing the workflow's successful-test dependency.
6. Vercel uses its GitHub integration to publish the frontend. Protect `main` with required CI checks so frontend production changes enter through tested pull requests.

No real credentials are embedded in the workflow. Its PostgreSQL password is isolated test-only data. Account-level Actions usage can incur costs outside your included allowance; inspect billing settings before expanding CI workloads.

## 9. Common failures and maintenance

| Symptom | Check |
|---|---|
| Browser cannot reach API | `VITE_API_URL`, HTTPS, backend wake-up, exact CORS origin, and Network-tab status |
| `/health` works but `/ready` fails | Supabase pause state, URL encoding, TLS, session-pooler username and migration version |
| Upload remains UPLOADED | No free worker is running; press Process or run the worker from your own machine against the same database |
| EMBEDDING fails | Space awake, correct key, exact `/embeddings` endpoint, expected 384 dimensions |
| Generated answers fail | Exact `/v1` URL and `sai-local` alias, provider availability, CPU timeouts, context/model limits |
| Answer is insufficient despite good retrieval | Inspect the grounding verdict; improve the model/prompt or corpus, not the metric display |
| SQL route fails | Separate reader credentials, view grant, manager/admin role, supported question template |
| Vercel still calls localhost | Rebuild after setting the build-time environment variable |
| Render runs out of memory | Ensure both model providers are `http`; do not load local models into the free API process |

Use synthetic data for the public portfolio. Delete old document versions by deleting an unneeded logical document, and remove old diagnostic data using an explicitly reviewed database-retention procedure. There is no automatic retention job yet. Keep backups appropriate to your data; provider free plans may not include the recovery features you expect.

Cloud Run is an optional container host, not part of this setup. It may require billing activation and can charge for compute, builds, registry storage, networking and related resources even when some free allowance exists. This application works without it, AWS, GCP, Kubernetes, paid Redis or paid vector databases.
