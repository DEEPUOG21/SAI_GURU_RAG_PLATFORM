# Build verification log

This record separates implemented features from checks actually executed. Verification used native Windows, Python 3.11, PostgreSQL 16.2 with pgvector, Chrome, real ONNX models and a local CPU LLM. No cloud deployment or Docker build is represented as tested.

## Phases 1–3: foundation, database and ingestion

React/TypeScript/Vite/Tailwind/Radix workspace and modular FastAPI API built. Initial frontend build/lint/test and backend health test passed. PostgreSQL models, composite tenant/document relationships, HNSW vectors, full-text GIN indexing and frozen Alembic migrations implemented. Both migrations were applied to native PostgreSQL.

Seven formats are supported: PDF, DOCX, TXT, Markdown, HTML, CSV and JSON. Structured parsers, page/section-aware chunks, incremental version hashes, durable processing states and worker implemented. Early ingestion suite: 16 tests passed. Final verification indexed all eight synthetic SaiTech documents using actual embeddings. Browser verification also uploaded, indexed, previewed and deleted a new document. Scanned-PDF OCR is unsupported.

## Phases 4–10: retrieval, generation, grounding, routing and SQL

Dense and lexical retrieval, actual RRF scoring, local cross-encoder reranking, bounded context, streamed drafts, citations, grounding, deterministic routing and read-only SQL implemented. Early retrieval suite: 21 tests passed. Final native integration checks exercised actual vector/full-text scores and local reranking, including authorization before retrieval. SQL execution used a separate restricted role; attempted DELETE and reading the users table were denied.

Real inference used BGE small embeddings, MiniLM cross-encoder reranking and Qwen2.5-1.5B-Instruct Q4_K_M. The earlier 0.5B experiment performed poorly; its actual results remain in `verification-small-model.json`. A negative test exposed an incorrect semantic approval by the 1.5B judge. A general numeric-literal guard now rejects values absent from cited evidence before model judgment. The deliberately incorrect 99-day leave claim is rejected. This guard and the model still do not guarantee factual correctness; see the pipeline documentation.

## Phases 11–13: security, evaluation and observability

Argon2 passwords, JWT authentication, database-backed roles/rate limits, tenant isolation, file/body limits and source-access rechecks implemented. Tests cover isolation across tenants and roles, private documents, stale sources, unsafe SQL, API errors and ingestion constraints. Query records retain actual node timings, candidates, scores, errors, usage availability and grounding outcomes.

The earlier real three-case evaluation completed against all eight indexed demo documents using the 1.5B model. `local-verification.json` records those actual answers, citations, configurations and traces. This single-turn baseline predates the conversation fixes and 3B model upgrade; its measured aggregate was:

| Metric | Result |
|---|---:|
| Recall@6 | 1.000 |
| Precision@6 | 0.167 |
| MRR | 1.000 |
| NDCG | 1.000 |
| Grounding pass rate | 1.000 |
| Answer relevance (token F1 proxy) | 0.517 |
| Context relevance (label proxy) | 0.556 |
| Citation correctness (document and section) | 1.000 |
| Mean end-to-end latency | 22.04 seconds |

Three synthetic questions are not a general benchmark. Grounding pass rate is model judgment, not human-verified accuracy. Token usage/cost remain unavailable when providers omit usage reports; no estimated token counts are substituted.

## Phases 14–16: containers, CI and free deployment

Backend/frontend Dockerfiles, persistent PostgreSQL Compose setup, migration/seed service, ingestion worker and optional authenticated CPU inference image provided. GitHub Actions defines frontend lint/type/tests/build/browser checks, backend lint/tests with a pgvector service, container builds, and an opt-in Render deployment hook. A detailed guide covers GitHub, Supabase, Hugging Face CPU inference, Render, Vercel, environment variables, CORS, quotas, cold starts and optional paid choices.

**Not executed:** Docker image builds/Compose startup (Docker and WSL are unavailable on this machine), remote GitHub Actions, and deployment to cloud accounts. These require validation in the documented environments before a public release. No repository was published and no paid service was activated.

## Final local checks

- Backend Ruff: passed.
- Backend unit/API/security/native integration suite: **84 passed**, including general-question, multi-hop follow-up and inherited source-access regressions.
- Frontend ESLint and TypeScript: passed.
- Frontend Vitest: **5 passed**.
- Vite production build: passed.
- Browser suite: **3 passed**, including the real API/inference flow and mobile navigation.
- Native migrations, eight-document indexing, real streamed/cited answer, negative numeric grounding case, restricted SQL and actual evaluation: passed.
- Clean frontend dependency install and npm audit: zero reported vulnerabilities at verification time.
- Local generated secrets are ignored and scanned against publishable files. No credentials were committed or published.

The application is runnable locally with real models and PostgreSQL. Container/cloud execution remains an explicit verification boundary, not a claimed success.

## General chat routing correction

The original DIRECT route only recognized a few examples, which wrongly sent ordinary knowledge questions to document search. General questions now use the LLM directly; explicit company/document questions and workplace topics retain retrieval. Follow-ups are resolved before classification. Live checks covered a general-history question, Python, a follow-up, and a cited annual-leave answer. General answers are ungrounded model knowledge, not verified facts; the small local model can produce factual errors. Routing remains heuristic and may misclassify ambiguous questions.

## Multi-turn verification — 2026-09-17

The original history loader discarded assistant answers. It now retains bounded user/assistant context, resolves follow-ups with the LLM, and uses the resulting standalone question for retrieval. General replies receive conversation messages; RAG generation receives the resolved question and fresh evidence, preventing old source labels from contaminating new answers. A deterministic fallback retains the original topic across multiple follow-ups if the resolver cannot rewrite them.

Source dependencies propagate through conversation-derived answers and are checked on history, generation and debugger access. Tests verify that deleting a source also hides later answers derived from it, even when those later answers have no displayed citations. General-knowledge labels survive conversation reloads. Missing evidence can produce explicitly labeled general guidance; unsupported drafts still undergo bounded correction and verification.

Real multi-turn tests exposed contradictory output and incorrect verification by the 1.5B model. The included inference default was upgraded to Qwen2.5-3B-Instruct Q4_K_M; its separate upstream model license is documented. This improves the tested scenarios but does not guarantee factual accuracy.

`backend/scripts/conversation_smoke.py` completed all eight real HTTP questions on the 3B service:

1. Identify Gandhi, then answer his birth date and birthplace through two successive pronoun follow-ups.
2. Answer annual-leave allowance, accrual and contractor eligibility with actual document citations.
3. Switch from the policy conversation to a Python question using general LLM knowledge.
4. Report missing sabbatical-policy evidence and provide labeled general next steps without fabricating the policy.

The same check verified persisted answer labels after reloading history. All **3 browser tests** passed, including the expanded live test that sends an accrual follow-up through the chat interface, checks its citations and opens the retrieval trace. Backend suite: **84 passed**. Frontend lint/type/build and **5 unit tests** passed. The publishable-file secret scan passed. Earlier single-turn evaluation figures above remain historical, not a benchmark for this new model configuration.
