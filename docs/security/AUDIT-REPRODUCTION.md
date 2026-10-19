# Reproducing the audit

Run from the repository root in PowerShell. RTK was unavailable on the audited machine; these are ordinary commands. Use a disposable **sai_guru_test** database. Never point test helpers at production. The local helpers require the already-installed optional pgserver package; Docker is an alternative described in DEPLOYMENT.md.

## Existing local environment

In separate terminals, keep these services running:

```powershell
.venv/Scripts/python.exe backend/scripts/local_test_database.py
.venv/Scripts/python.exe scripts/run_local_inference.py
```

The native PostgreSQL helper can time out during recovery; inspect its log and rerun after the database is ready. Do not delete the database directory. Prepare the test URL, migrate an empty database, and provision the SQL reader using the existing private `.env` configuration:

```powershell
.venv/Scripts/python.exe backend/scripts/prepare_test_database.py
$env:DATABASE_URL = Get-Content .local-test-url -Raw
.venv/Scripts/alembic.exe -c backend/alembic.ini upgrade head
.venv/Scripts/python.exe -m app.database.setup_sql
```

The live audit creates isolated synthetic tenants and removes those fixtures. The supplementary evaluation uses the existing seeded synthetic workspace. Do not run the broader `system_smoke.py` to reproduce this audit against user-modified demo data: that script reseeds documents.

```powershell
.venv/Scripts/python.exe backend/scripts/security_audit_live.py
.venv/Scripts/python.exe backend/scripts/audit_injection.py
.venv/Scripts/python.exe backend/scripts/audit_supplement.py
```

Inspect JSON statuses: the live audit intentionally writes FAIL results without raising a failing process exit code. Baseline evidence is preserved in `audit/live-baseline.json`; `audit/live-results.json` contains the follow-up fix retest. The baseline login-limit probe sent only six requests after the earlier counter had expired; the corrected probe sends twelve consecutive attempts. That initial failure was a test-design defect, not proof the limiter was broken.

## Full application checks

```powershell
$env:DATABASE_URL = Get-Content .local-test-url -Raw
$env:SAI_INTEGRATION = '1'
$env:FASTEMBED_CACHE_PATH = (Resolve-Path .model-cache).Path
.venv/Scripts/ruff.exe check backend
.venv/Scripts/pytest.exe backend/tests -q --cov=backend/app --cov-report=json:docs/audit/coverage.json --junitxml=docs/audit/backend-tests.xml
```

Start `.venv/Scripts/python.exe scripts/run_verified_backend.py` separately for the live browser test, then:

```powershell
Set-Location frontend
npm ci
npm run lint
npm run typecheck
npm test
npm run build
npx playwright test
$env:SAI_E2E_LIVE = '1'
npx playwright test e2e/live-backend.spec.ts
```

Default browser tests mock API data and skip the live test; the explicit second command exercises real login, upload, processing, deletion and cited generation. Test credentials are read privately from `.env`.

## Security checks

Gitleaks 8.30.1 and Trivy 0.74.0 Windows binaries were downloaded from their official GitHub releases and checked against release SHA-256 files, into ignored `.local/tools/security`. Python tooling: pip-audit 2.10.1, Bandit 1.9.4, pytest-cov 7.1.0.

```powershell
.local/tools/security/gitleaks.exe dir . --config .gitleaks.toml --redact --report-format json --report-path .audit-gitleaks-final.json
.venv/Scripts/pip-audit.exe --format json --output .pip-audit-final.json
.venv/Scripts/bandit.exe -r backend/app inference -f json -o .bandit-final.json
.venv/Scripts/pip.exe check
npm audit --prefix frontend --json
.local/tools/security/trivy.exe fs --cache-dir .local/tools/security/trivy-cache --scanners vuln,misconfig --skip-dirs .venv --skip-dirs .model-cache --skip-dirs .local-postgres --skip-dirs .local --skip-dirs frontend/node_modules --format json --output .audit-trivy-final.json .
```

Expected nonzero results must be reviewed: Gitleaks sees three ignored local `.env` credentials; pip-audit sees diskcache; Bandit reports container bindings and a token-type false positive. Do not blanket-ignore new results. Once this directory is a Git repository, also run `gitleaks git . --redact` to scan history. Never publish unredacted reports or `.env`. Rotate any credential discovered in published history, then coordinate history cleanup; deletion alone is insufficient.

Docker commands below are **NOT VERIFIED locally** because Docker is not installed:

```powershell
docker build -f backend/Dockerfile -t sai-guru-api .
docker build -f frontend/Dockerfile -t sai-guru-web .
docker build -f inference/Dockerfile -t sai-guru-inference .
trivy image --severity HIGH,CRITICAL --exit-code 1 sai-guru-api
trivy image --severity HIGH,CRITICAL --exit-code 1 sai-guru-web
trivy image --severity HIGH,CRITICAL --exit-code 1 sai-guru-inference
docker compose up --build
```

Semgrep and CodeQL were **NOT RUN**. Suggested next source check on a supported environment: `semgrep scan --config p/python --config p/typescript --config p/security-audit backend frontend/src inference`. Review downloaded rules before use. Enable CodeQL Python and JavaScript/TypeScript analysis where the repository's GitHub plan permits; no paid service is required by this project.

## Deployment checklist

- [ ] Replace runtime database owner/superuser credentials with a tested least-privilege role; design and test tenant RLS and migration-owner separation.
- [ ] Supply strong distinct JWT, seed, reader and inference secrets through host secret settings. Keep only public API URL in `VITE_*`.
- [ ] Set exact HTTPS frontend origin in CORS; require database TLS and restricted network access; confirm Supabase anon/authenticated cannot access app tables or analytics view.
- [ ] Set `GENERATION_MODE=llm`, LLM URL/model/key and SQL_DATABASE_URL explicitly when enabling those features. The current Render manifest defaults to extractive and does not provision these settings.
- [ ] Resolve RAG conflicts/ambiguity and complete adversarial prompt tests with actual injected context and realistic documents.
- [ ] Add hard concurrency, memory and parser-process isolation limits; test overload, cancellation, cold starts and proxy timeouts.
- [ ] Configure CSP and HTTPS-only HSTS at the serving edge; verify actual response headers and SSE buffering in a deployed browser.
- [ ] Build all images, scan OS/runtime dependencies, verify non-root startup/health checks and writable cache paths. Pin image digests and complete transitive dependency locks.
- [ ] Make security checks required before deployment. Separate security workflow success is not currently a dependency of the optional deploy job.
- [ ] Define retention, deletion of derived traces, backup/restore and log access policies; test restoration and revocation.
- [ ] Verify current free-host limits and model license suitability manually; no hosted deployment or plan limits were verified here.
