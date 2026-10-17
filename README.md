# Sai Guru

**AI Knowledge Intelligence Platform** — a full-stack, evidence-first knowledge assistant for the fictional company SaiTech.

React, TypeScript, Vite, Tailwind and Radix UI power the workspace. FastAPI coordinates document ingestion, PostgreSQL/pgvector hybrid retrieval, local ONNX embeddings, cross-encoder reranking, streamed LLM generation and grounding verification. There are no fabricated dashboard metrics or canned AI answers.

> Release status: the application has local verification and security hardening, but container-image advisories and hosted end-to-end verification remain open. See [release readiness](docs/RELEASE-READINESS.md).

## Start locally

Install Python 3.11+, Node 22+, Docker Desktop/Engine with Compose, and optionally Ollama. Run these commands from this repository's root:

```sh
python scripts/configure_local.py
docker compose up --build
```

The setup script creates an ignored `.env` with unique credentials. Compose starts PostgreSQL, applies migrations, creates restricted runtime and read-only SQL accounts, seeds eight synthetic documents and an admin, and serves the application. Process uploads from the UI, or enable the optional `worker` profile with `WORKER_TENANT_ID` set to the tenant UUID.

- Frontend: http://localhost:5173
- API and OpenAPI: http://localhost:8000/docs
- Liveness: http://localhost:8000/api/v1/health
- Database readiness: http://localhost:8000/api/v1/ready
- Login email: `SEED_ADMIN_EMAIL` in `.env`; password: `SEED_ADMIN_PASSWORD` in `.env`.

For real local AI generation, install Ollama and run `ollama pull qwen2.5:3b` on the host. Ensure Ollama accepts connections from Docker (see [local development](docs/LOCAL-DEVELOPMENT.md)). Alternatively, use the included CPU inference service. If you do not have an LLM, set `GENERATION_MODE=extractive` in `.env` and recreate the backend. This returns **actual quoted excerpts**, clearly labeled as extractive search, and does not pretend to generate AI answers.

## Explore the product

1. Open **Knowledge Library**. Wait for the seeded documents to finish, or upload your own supported files. Managers/admins can upload, process, retry and delete.
2. Ask **“What is our annual leave policy?”** in Knowledge Assistant. Watch the provisional draft stream; the final answer replaces it after verification.
3. Open a source card to inspect the exact document text, section, available page number and chunk ID.
4. Select **Inspect retrieval** to see routing, timings, retrieval scores, RRF, reranking, context and grounding.
5. Run **Evaluations** to establish a measured baseline against three synthetic cases. Methodology is visible because some generation metrics are explicitly labeled proxies.
6. Return to **Overview** to see actual indexed-document and query activity.

## Repository

```text
frontend/                 React workspace, UI tests, browser tests, Dockerfile
backend/app/
  api/                    Versioned HTTP routes
  core/                   Validated environment settings
  database/               Sessions, seeding and SQL role setup
  models/                 Relational schema
  schemas/                Pydantic request validation
  ingestion/              Parsers, structured chunking, durable worker
  retrieval/              Dense, lexical and reciprocal-rank fusion
  reranking/              Local/HTTP reranker providers
  agents/                 Deterministic workflow, routing, safe SQL
  evaluation/             Dataset runner and metrics
  observability/          Bounded execution trace
  security/               Authentication, roles, body/rate limits
  services/               Generation, grounding, context, streaming and access
backend/migrations/       Frozen Alembic migrations
backend/tests/            Unit, API, security, integration and regression tests
data/                     Eight synthetic policies and evaluation labels
inference/                Optional authenticated CPU model service
docs/                     Setup, design, deployment and verification records
.github/workflows/        CI checks and opt-in deployment trigger
```

## Documentation

- [Current hardening results and release blockers](docs/HARDENING-RESULTS.md)
- [Setup](docs/SETUP.md) — prerequisites and environment variables
- [Local development](docs/LOCAL-DEVELOPMENT.md) — separate processes, migrations, seeds and tests
- [Free deployment](docs/DEPLOYMENT.md) — GitHub → Supabase → model host → Render → Vercel
- [Architecture](docs/ARCHITECTURE.md) and [RAG pipeline](docs/RAG-PIPELINE.md)
- [Evaluation methodology](docs/EVALUATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Verification and limitations](docs/PROGRESS.md)

## Honest boundaries

This is a tested portfolio application, not a claim of production scale. Authentication is password + one-hour bearer JWT; there is no password-reset email or SSO. Scanned-PDF OCR is not implemented. DOCX and text formats have no invented page numbers. SQL supports four audited analytics templates, not arbitrary natural-language SQL. The local cache abstraction is optional and deliberately not used for authorization-sensitive result caching.

Conversation context includes both user and assistant turns; follow-ups are resolved before retrieval. General answers and optional missing-evidence guidance are visibly labeled as not source-verified. Set `GENERAL_FALLBACK_ENABLED=false` for strict abstention when documents cannot answer. Source access is rechecked for prior answers and answers derived from them.

Grounding verification is model-based and can be wrong. Provisional text is visibly marked until verified. Model outages are surfaced; dense/reranker fallbacks are recorded. Free hosting can sleep, pause, exhaust quota or change terms. No paid API, Redis, Kubernetes or dedicated vector database is required. Docker builds and live cloud deployment must be checked on a machine/account with those capabilities; consult the verification log for checks actually performed.

MIT licensed application code. Model weights retain their upstream licenses.
