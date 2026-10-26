# Sai Guru

A knowledge assistant with document search, cited answers, conversational follow-ups and structured company analytics.

React and TypeScript provide the workspace. FastAPI and LangGraph coordinate PostgreSQL/pgvector hybrid retrieval, reranking, streamed generation and grounding checks. LangSmith provides optional private tracing and experiment comparison.

## Run locally

Requires Python 3.11+, Node 22+ and Docker Compose.

```sh
python scripts/configure_local.py
docker compose up --build
```

Open `http://localhost:5173`. API documentation is at `http://localhost:8000/docs`. Sign in with `SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD` from your private `.env`.

Configure a model before asking generated questions. The default local provider uses Ollama with `qwen2.5:3b`; hosted inference is covered in [deployment](docs/deployment.md). `GENERATION_MODE=extractive` enables quoted search excerpts without a generation model.

## Project layout

```text
backend/       API, migrations and tests
frontend/      React application and UI tests
inference/     Optional CPU model service
data/          Demo documents and benchmark
scripts/       Setup, validation and evaluation commands
docs/          Development, design, deployment and evidence
```

Docker Compose and Render configuration stay at the root; CI workflows live in `.github/`. Private configuration, dependencies, databases, model caches and local archives are ignored by Git.

## Documentation

- [Development](docs/development.md): setup, migrations, inference and tests
- [Architecture](docs/architecture.md): design, access boundaries and RAG workflow
- [Deployment](docs/deployment.md): database, hosted models, API and frontend
- [Observability](docs/observability.md): LangGraph and LangSmith
- [Evaluation](docs/evaluation.md) and [recorded evidence](docs/evidence/README.md)
- [Troubleshooting](docs/troubleshooting.md) and [security policy](SECURITY.md)

## Validation

```sh
python scripts/check_repository.py
python -m pytest backend/tests -q
cd frontend
npm test
npm run lint
npm run build
```

Database integration tests require a disposable `sai_guru_test` database. See the development guide before enabling them.

## Scope

Answers expose their sources and grounding status. General guidance is labeled when it is not source-verified. Grounding checks can still be wrong; evaluate on your own corpus. The included eight-case benchmark measures synthetic company policies.

Guardrails screen inputs and retrieved text, mask supported sensitive formats before provider calls, enforce tool permissions and check output before display. Decisions are visible in Retrieval Lab. See the [policy and limitations](docs/observability.md#guardrail-policy).

Authentication uses password sign-in and bearer JWTs. OCR, password-reset email and SSO are not implemented. SQL analytics use audited templates. Evidence records describe tested behavior and limitations.

MIT licensed. Model weights retain their upstream licenses.
