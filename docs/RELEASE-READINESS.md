# Release readiness

This repository contains the application source, migrations, tests, pinned dependency locks, CI security gates, and hosting configuration. It does not contain local credentials, model weights, database files, generated frontend bundles, or installed dependencies.

## Layout

- `backend/`: FastAPI application, database migrations, backend tests and operational scripts.
- `frontend/`: React application, unit/browser tests and Vercel/Nginx configuration.
- `inference/`: Optional authenticated CPU embedding, reranking and LLM service.
- `data/`: Synthetic demonstration documents and evaluation dataset.
- `scripts/`: Local configuration and launch helpers.
- `docs/`: Architecture, operating guides and historical audit evidence.
- `.github/`: Validation, security workflows and dependency updates.

## Open release requirements

- Build and scan the actual application images. Earlier Python base-image HIGH advisories remain documented; the security gate must not be bypassed to obtain a green release.
- Review the optional inference `diskcache` advisory; disk caching is disabled, but that does not remove the dependency advisory.
- Configure the model service and index uploaded documents before claiming working document retrieval in a hosted environment.
- Verify hosted login, uploads, citations, follow-ups, streaming, tenant isolation, backups and retention.
- Configure exact CORS/CSP origins and hosting deployment checks. A successful source upload is not a production deployment.

## Supabase provisioning

Provision only a dedicated project with the application migrations already applied. Set `SUPABASE_PROJECT_REF` and `SUPABASE_POOLER_HOST` from its Connect dialog; the host cannot be inferred from the region. Save its owner password locally in `.env.supabase-password` and its official database CA certificate in `.env.supabase-ca.crt`. These files are ignored by Git and Docker.

Run `python backend/scripts/provision_supabase.py` from the repository root. It writes restricted runtime credentials and initial admin credentials into the ignored `.env.supabase`; it never prints those values. Then run `python backend/scripts/verify_supabase.py` to verify login and database boundaries.

For deployed connections, use `ssl=verify-full` and provide the CA through `PGSSLROOTCERT` at a path available on the host. The local helper uses a local certificate path; deploy that certificate separately with your hosting configuration. Do not deploy the owner password to the API.

Historical local validation is described in `HARDENING-RESULTS.md`. Run CI on the uploaded revision for current results.
