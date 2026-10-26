# Troubleshooting

## API or frontend won't start

Run Python commands from the repository root with the virtual environment activated. A `ModuleNotFoundError: app` means `pip install -e './backend[dev,local]'` was not installed into the interpreter being used. Run `python -m pip --version` to check its path. The backend's health route works without models, but authenticated features require configured PostgreSQL and `JWT_SECRET`.

Run `npm ci` in `frontend`, then `npm run typecheck` and `npm run build`. Vite/esbuild/Playwright need to spawn child processes. In restricted Windows shells, `spawn EPERM` indicates a process restriction, not necessarily a TypeScript bug. Use a terminal permitted to run build tools. Do not disable security tooling globally.

## Database connection or migration errors

- Docker must be running. `docker compose ps` shows the database health; `docker compose logs db migrate` reveals startup errors.
- Use `postgresql+asyncpg://`, the correct database name, percent-encoded credentials, and the correct host. Inside Compose the database host is `db`; outside it is localhost.
- On Supabase use the session pooler or a suitable direct connection. The transaction pooler is not compatible with this application's session advisory-lock design.
- `type vector does not exist`: enable the vector extension and ensure its schema is in the connection's search path.
- `relation ... does not exist` or `/ready` returns 503: apply all migrations. Expected head is `0002`.
- `password authentication failed`: distinguish the main app role, the SQL-reader role and the login account. They are three separate credentials.

Never work around a failed reader connection by giving the SQL tool the admin URL. The API rejects that configuration deliberately.

## Sign-in errors

The seed command creates an admin only when that email does not already exist. It does not reset existing passwords. Confirm that seed and backend point at the same database. `SEED_ADMIN_PASSWORD` is private configuration, not a built-in default password.

JWT sessions expire after one hour. Sign in again. Changing `JWT_SECRET` invalidates all sessions. The UI stores bearer tokens in sessionStorage; changing browser tabs or clearing storage can require another login. There is currently no password-reset or SSO flow.

## Upload or ingestion errors

Supported formats are PDF, DOCX, UTF-8 TXT/Markdown/HTML/CSV/JSON. A changed suffix does not make an executable a valid PDF or DOCX. PDFs need extractable text; scans require external OCR before upload. DOCX expanded size is capped, PDFs are limited to 500 pages, extracted text to two million characters, and documents to 5,000 chunks.

UPLOADED means the bytes are stored and waiting for processing. Run `python -m app.ingestion.worker` or select Process. EMBEDDING can take longer during first model download. FAILED entries include a safe message; inspect worker logs, correct the dependency/provider, and retry with Process. Original bytes remain in the database.

The same filename is a logical document. An identical successful upload is reused; changed bytes or access create another version. Replacement hides previous chunks until the new version completes. Do not change embedding models/dimensions without reindexing and, for different dimensions, a schema migration.

## Retrieval and answer errors

Use the query ID from the response or Inspect retrieval. Check classification, rewritten question, dense/lexical scores, RRF, reranker and final-context chunk IDs. A policy question about a number of leave days should route DOCUMENT, while employee headcount goes to SQL. Routing is deliberately heuristic; complex ambiguous questions may need rephrasing.

Unavailable dense/reranker providers produce explicit degraded trace entries. An LLM timeout/provider error produces a failed query, not a fabricated response. An insufficient answer can mean missing evidence, insufficient permissions, missing citations, unsupported claims or a weak verifier. It is not evidence that a synthetic policy has changed.

Scores from dense, lexical, fusion and reranking are not interchangeable probabilities. A positive dense match alone does not prove the source answers the question. Grounding remains a fallible model-based check; inspect the source.

If a source was deleted, replaced or became restricted, old answer text is redacted on history/debug reads. Regenerate against the current corpus. This behavior prevents historical copies from bypassing current source access.

## Streaming issues

Reverse proxies must avoid buffering `text/event-stream`. FastAPI sends keepalives and `X-Accel-Buffering: no`. The browser shows progress while the answer remains private, then displays the checked final answer. If the connection ends without a valid terminal event, it reports an error. Check the backend query record before retrying: an answer may have been stored even if its final network frame did not reach the browser.

CPU generation can exceed free-host timeouts. Wake the model service before a demo, use a manageable model, and configure a bounded `QUERY_TIMEOUT_SECONDS` up to 600. Do not assume increasing the timeout fixes an out-of-memory error.

## Evaluation results look low or unavailable

Seed/index the exact demo documents first. Precision@6 has a maximum of 1/6 when a case labels only one relevant document. Answer relevance is token F1, context relevance uses document labels, and faithfulness is a grounding pass rate. These methods are documented and are not invented semantic measures. Null token usage means the provider did not report it. A failed run may show partial cases; do not treat it as a complete baseline.

## Docker and free-host issues

Use `docker compose config` to validate interpolation without publishing its output: it includes resolved secrets. Never attach that output to an issue. `docker compose up --build` requires internet and a Docker daemon. This workspace's original Windows environment lacked Docker/WSL, so native PostgreSQL was used for database verification; Docker build jobs are included in CI.

Render and model Spaces can sleep, and Supabase can pause free projects. Check provider status and quotas rather than fabricating uptime indicators. The top bar reports database readiness only. The app remains usable in explicitly selected extractive mode if a generative model is unavailable, provided document retrieval providers are configured.
