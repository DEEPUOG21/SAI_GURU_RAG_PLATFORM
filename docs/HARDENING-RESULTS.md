# Sai Guru hardening results

Updated September 21, 2026. This is the current follow-up to [the initial security audit](SECURITY-AUDIT.md). **Local hardening is implemented and tested; a production release is still blocked by upstream image advisories and unavailable deployment access.** No production-readiness or compliance certification is claimed.

## Verified outcome

- **127 backend tests passed, zero failures/skips**, including real PostgreSQL RLS, token revocation, evaluation isolation, deletion/retention and parser subprocess tests. Statement coverage: **78.6150%** of the expanded codebase; this is not branch or subprocess coverage. [JUnit](audit/hardening-tests.xml), [coverage](audit/hardening-coverage.json).
- **7 frontend unit tests passed**, ESLint, TypeScript and Vite production build passed. **All 3 Playwright tests passed**, including real login, upload, isolated parsing/indexing, source preview, deletion, cited chat and follow-up using the restricted database account.
- **33 functional probes passed** in the broad real-model audit. Eleven of twelve RAG predicates passed initially; multi-document generation produced citation placeholders instead of values. That defect and a subsequent fallback-ranking defect were corrected, with a separate [successful final multi-document retest](audit/multiple-document-final.json). Earlier failures are retained in [the broad run](audit/live-results.json) and [intermediate retest](audit/multiple-document-retest.json). Do not describe these as one all-green twelve-case run.
- [The strengthened injection probe](audit/injection.json) confirms malicious instructions reached context. It returned the relevant office-location fact without the attack canary through **explicitly labeled verbatim excerpts**, because the small model's semantic judge still rejected a valid paraphrase. This is useful fallback behavior, not proof of universal prompt-injection resistance or a successful generated-answer judgment.
- The partial retest's twelve-login burst crossed a fixed-window boundary, so its limiter predicate failed. A [fresh 21-request probe](audit/rate-limit-final.json) correctly reached 429. The audit script now uses 21 attempts to cover a possible boundary; previous failed evidence has not been erased.
- Complete hashed backend runtime lock: **no known advisories found** by pip-audit. Trivy filesystem/configuration scan: **no reported vulnerabilities or misconfigurations in its five scanned targets**. These results do not replace installed inference or image scans. [Scanner summary](audit/scanner-summary.json).

## Database isolation and runtime privileges

Migrations `0003` and `0004` add forced tenant RLS to twelve application tables and account token-version counters. [Runtime database evidence](audit/runtime-database.json) records `sai_runtime` with superuser, bypass-RLS, create-role and create-database all false, plus enabled/forced RLS on all twelve tables. The API refuses startup with a superuser/bypass-RLS or document-table-owner account. Its actual native startup succeeded with the runtime role.

Tenant identity is applied transaction-locally and reapplied after each commit. Tests deliberately omit tenant WHERE filters, attempt cross-tenant inserts, commit repeatedly, reuse pooled connections and try disabling RLS. Unscoped reads return no documents; cross-tenant writes and policy changes fail. Populated evaluation results are isolated between tenants. Authentication has a separate SELECT-only identity lookup policy before the tenant is established; it does not authorize tenant writes.

Application role/ownership checks remain necessary: database policies are a **tenant boundary**, not a substitute for document-level minimum-role checks or per-user ownership. A party holding runtime database credentials can set the tenant GUC; these policies defend against missing application filters, not a fully compromised application process or stolen database credentials. Keep migration/owner credentials out of the API. The separate SQL reader remains read-only with its scoped analytics view.

`setup_runtime` provisions the role; native preview reads ignored `.local-runtime-url`. Compose migrates/seeds using owner credentials and runs API/optional tenant-scoped workers as `sai_runtime`. Grant changes must be reapplied after migrations that introduce new tables. Dedicated workers require `WORKER_TENANT_ID` and are opt-in under the Compose `worker` profile; authenticated request-driven processing remains available.

## Resource limits and parser isolation

Uploads parse in disposable subprocesses, with a **512 MiB process memory limit**, **30-second wall deadline**, and Linux **25-second CPU limit**. Windows uses a Job Object; Linux uses resource limits. Timeout/cancellation kills and waits for the child. Provider/database secrets are not forwarded in its environment. Tests cover successful parsing, malformed JSON and forced timeout termination. DOCX archive entries are capped at 2,048 in addition to the existing 40 MiB expanded cap.

Two heavy-work slots are shared across API processes and background workers through PostgreSQL advisory locks; slots last through complete SSE responses. Missing/invalid JWTs are rejected before reserving capacity or reading an expensive request body. Real database-lock tests prove saturation returns 429/Retry-After. Body buffers are coalesced, with a 15-second deadline; non-upload bodies are capped at 64 KiB, uploads at configured file size plus multipart allowance. Existing per-user/IP rate limits remain.

This is resource isolation, **not a complete OS security sandbox**: parsers still run under the service account and inherited filesystem/network permissions. Linux container behavior, hostile-file corpora, prolonged multi-host load and proxy cancellation behavior still require execution tests. External LLM services need their own admission limits; local CPU generation is deliberately modest.

## Authentication and privacy

`POST /api/v1/auth/logout` increments the account's token version and invalidates all existing tokens for that account. React completes server revocation before clearing its local token. A copied token was rejected after logout in the real runtime-role test.

`DELETE /api/v1/conversations/{id}` permanently deletes an owned conversation's messages, queries, feedback and retrieval results. Cross-tenant deletion is denied. A confirmation dialog is available in the assistant. Document deletion now removes stored derived queries/messages/evaluations referencing the source, including inherited history dependencies, instead of only masking them at read time. Integration tests verify removal. Content already transmitted to clients or external providers cannot be recalled.

`python -m app.database.retention --tenant TENANT_ID --days 30` previews expired history. `--apply` performs explicit tenant-scoped deletion. Tests prove preview does not delete and apply preserves fresh history and the other tenant. **No production retention job was scheduled and no existing user history was purged by this work.** Operators must select/schedule their policy and separately manage backups, provider retention and log retention.

Exception handlers no longer log arbitrary exception tracebacks/messages, reducing password/provider/parser payload disclosure. SQL setup failures suppress password-bearing DDL exception text. Logs retain stable failure IDs/types where available. Backup encryption, host ACLs, account recovery/MFA and hosted log access remain outside the verified local implementation.

## RAG correctness

- Follow-ups preserve the company route when rewriting loses words such as “our.” Explicit topic changes remain supported.
- Underspecified “What is our policy?” asks for a topic instead of inventing a policy or merging unrelated sources.
- Identical sentence structures with conflicting numeric values in different relevant sources are quoted side by side; no authoritative/current version is invented. This is a conservative numeric conflict check, not a general semantic conflict solver.
- Citation placeholders cannot replace actual facts, dates or quantities. Malformed drafts are rejected before the model judge.
- When generation remains unverifiable, relevant excerpts preserve semantic retrieval ranking and are clearly marked **EXTRACTIVE**, with trusted source metadata. The rejected generated answer is not published as verified. The fallback does not repeat recognized instruction-like sentences, but this filter is not an authorization mechanism or universal injection detector.

The local 3B model can still hallucinate or misjudge paraphrases. The initial three-case evaluation's 66.7% generation-grounding score is historical and is **not relabeled as current 100% model accuracy**. Real-source testing and human evaluation remain necessary for deployment-specific quality claims.

## Frontend, API and deployment configuration

Markdown images remain blocked in drafts/finals, unsafe HTML/URLs are rejected, and outbound links use noopener/noreferrer. CSP is now configured for Nginx and Vercel; Vercel also gets HTTPS HSTS. CSP permits HTTPS API connections and local development API ports; tighten `connect-src` to the actual deployment origin once known. Hosted/browser enforcement of these edge headers is not verified; Vite dev responses do not exercise production Nginx/Vercel headers.

Public response contracts now cover auth, documents, conversations/messages, dashboard, retrieval debugging and evaluation listings. Common error envelopes and the SSE response/media type/event description are included in [updated OpenAPI](audit/openapi.json). Dynamic trace/result payloads intentionally remain JSON objects.

The document upload UI reads its size limit from API health metadata. API/frontend/inference Docker health checks are configured; all three application images specify non-root users. Python, Node, Nginx and pgvector references are pinned to [registry-resolved digests](audit/base-image-digests.json). Backend installation uses a complete cross-platform hash lock, retaining tested versions. Python build-tool versions are upgraded explicitly in Docker configuration. Render now explicitly requests LLM mode/model/URL/key and the SQL reader URL rather than silently deploying extractive mode.

The main CI workflow calls the security workflow and makes its success a dependency of optional deployment. Gitleaks, Bandit, pip-audit, npm audit and Trivy gates are configured; reviewed Semgrep rules and pinned CodeQL workflow have been added. CodeQL is restricted to public repositories so no paid private-repository feature is required. Dependabot remains configured. YAML parses successfully. **Remote workflow execution is not verified**, and Vercel's independent Git integration must be configured to honor required checks before production deployment.

## Current scanner findings and release blockers

| Area | Result / remaining action |
|---|---|
| Backend runtime lock | pip-audit found no known advisories; complete transitive versions and hashes included |
| Local secrets | Gitleaks reports four actual credentials only in ignored `.env`; no application-source match. No credentials printed or published |
| Bandit | No HIGH findings; two intentional all-interface inference bindings MEDIUM; `token_type="bearer"` and null token usage LOW false positives |
| Trivy filesystem/config | No findings reported in five targets; not an application image build/scan |
| Nginx pinned base image | Remote scan reports zero HIGH/CRITICAL findings |
| Python pinned base image | **46 package findings / 10 unique HIGH advisory IDs**. Eight IDs concern upstream OS packages with no fixed version listed; two concern inherited Python build tooling. Docker tooling upgrades address the latter in configuration, but a built-image scan is still needed |
| Alternative Python Bookworm base | Compared rather than blindly switching: 62 package findings / 23 unique IDs, so it was not adopted |
| Optional inference dependency | diskcache 5.6.3 advisory remains; disk caching is explicitly disabled. No fixed version was reported. No unsupported claim of removing the package |
| Docker/Compose | Local Docker engine unavailable; application image builds, startup and full-image scans **NOT VERIFIED** |
| Git history / cloud / Actions | No local Git repository or available browser session. Project names/URLs and authenticated hosting access were requested but not supplied; checks **NOT VERIFIED** |

[Base-image findings](audit/base-image-scans.json) retain package versions, IDs, fixed-version fields and advisory links. OS findings are inherited scanner results; application exploitability has not been established. They are **not suppressed**, and the HIGH/CRITICAL image gate intentionally prevents a false green release. A clean source scan is not a clean image scan.

## Reproduce the hardened local environment

Keep native PostgreSQL running in one terminal, then use owner credentials only for setup:

```powershell
.venv/Scripts/python.exe backend/scripts/local_test_database.py
```

In another terminal:

```powershell
.venv/Scripts/python.exe backend/scripts/prepare_test_database.py
$env:DATABASE_URL = Get-Content .local-test-url -Raw
.venv/Scripts/alembic.exe -c backend/alembic.ini upgrade head
.venv/Scripts/python.exe -m app.database.setup_sql
.venv/Scripts/python.exe backend/scripts/configure_runtime.py
$env:SAI_INTEGRATION = '1'
$env:FASTEMBED_CACHE_PATH = (Resolve-Path .model-cache).Path
.venv/Scripts/pytest.exe backend/tests -q --cov=backend/app
```

Start `.venv/Scripts/python.exe scripts/run_local_inference.py` and `.venv/Scripts/python.exe scripts/run_verified_backend.py` in separate terminals. The API launcher selects the runtime URL automatically. Existing `.env` credentials remain private. Then:

```powershell
Set-Location frontend
npm run lint
npm run typecheck
npm test
npm run build
$env:SAI_E2E_LIVE = '1'
npx playwright test
```

The initial [reproduction guide](AUDIT-REPRODUCTION.md) provides scanner commands; this document supersedes its owner-account startup and earlier open-finding descriptions. The native test-helper recovery timeout is a development-tool limitation: wait for PostgreSQL recovery, then rerun the helper instead of deleting its data.

## Remaining completion requirements

1. Provide the existing Vercel, Render and Supabase project URLs/names and make their authenticated sessions available. No cloud changes have been guessed or applied.
2. Build and scan the actual images in Docker/CI; address or explicitly assess the upstream base-image and optional inference advisories. Do not bypass the configured gate to claim success.
3. Verify deployed TLS, exact CORS/CSP origins, database network access/roles, migrations, proxy streaming, cold starts, provider limits and backups. Check Vercel deployment gating separately.
4. Select and schedule retention, verify backup/restore and run deployment-specific load/adversarial tests. The implemented safeguards and passing synthetic tests do not eliminate all future model or parser risks.
