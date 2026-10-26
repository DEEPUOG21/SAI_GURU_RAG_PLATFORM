# Deployment

The application uses Vercel for the frontend, Render for the API and Supabase PostgreSQL with pgvector. Cloudflare Workers AI supplies the hosted chat, embedding and reranking models. Check provider availability and account limits in the relevant dashboards.

## Database

Apply `backend/migrations/` with a provisioning account. Provision runtime and SQL-reader roles through `app.database.setup_runtime` and `app.database.setup_sql`. The API uses the restricted runtime role; analytics use the separate reader URL. Keep owner credentials out of the runtime service.

Store `DATABASE_URL` and `SQL_DATABASE_URL` only in the backend environment. Use verified TLS with the database CA configured through `PGSSLROOTCERT`.

## Hosted models

Set these API environment values using the intended Cloudflare account and its private Workers AI token:

```dotenv
EMBEDDING_PROVIDER=http
EMBEDDING_URL=https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/v1/embeddings
EMBEDDING_MODEL=@cf/baai/bge-small-en-v1.5
EMBEDDING_DIMENSIONS=384
RERANKER_PROVIDER=cloudflare
RERANKER_URL=https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/run/@cf/baai/bge-reranker-base
RERANKER_MODEL=@cf/baai/bge-reranker-base
INFERENCE_API_KEY=PRIVATE_WORKERS_AI_TOKEN
LLM_URL=https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/v1
LLM_PROVIDER=cloudflare
LLM_MODEL=@cf/meta/llama-3.3-70b-instruct-fp8-fast
LLM_API_KEY=PRIVATE_WORKERS_AI_TOKEN
GENERATION_MODE=llm
GENERAL_FALLBACK_ENABLED=true
GROUNDING_ACTION=regenerate
QUERY_TIMEOUT_SECONDS=300
```

Use a token restricted to the intended account. Reindex when changing embedding providers. Do not expose tokens through frontend variables.

## Render API

The blueprint is `render.yaml`; the Docker build uses the repository root and `backend/Dockerfile`. Configure database, JWT, model settings and the exact HTTPS frontend origin privately. The Cloudflare settings above override the blueprint's generic HTTP reranker default.

Keep `JWT_SECRET` stable across normal redeployments. Set `CORS_ORIGINS` to the actual frontend origin. If the CA is stored as a secret file, set `PGSSLROOTCERT` to its runtime path. Deploy the intended commit and check `/api/v1/health` and `/api/v1/ready`.

Uploaded bytes and job state persist in PostgreSQL. Knowledge Library supports request-driven processing. The optional worker requires an explicit tenant scope. Backend changes require a Render deployment even when the frontend has deployed automatically.

## Vercel frontend

Import the repository with `frontend` as the project root and use its Vite build configuration. Set `VITE_API_URL` to the public API origin before building. `frontend/vercel.json` contains routing and response headers. Changes to `VITE_*` values require a new build.

## Tracing and evaluation

Store the optional LangSmith API key only in the backend environment and keep input/output hiding enabled for runtime traces. See [observability](observability.md).

The demonstration benchmark is bundled in `data/demo/evaluation.json`; a private override belongs in ignored `data/evaluation.json`. See [evaluation](evaluation.md).

## Release checks

1. Confirm the intended commit is live and database readiness succeeds.
2. Verify sign-in, denied anonymous requests and CORS.
3. Upload a disposable document, process it, and require a cited answer from its content.
4. Check greetings, follow-ups, general questions and missing company facts. SSE must include a final answer or explicit error followed by `done`.
5. Run the benchmark and inspect citations, grounding and trace delivery.
6. Remove disposable test records and record failures as well as successful reruns.

Measured results are retained in [evidence](evidence/README.md). Account-specific deployment records and diagnostics belong in private `.local/` storage.
