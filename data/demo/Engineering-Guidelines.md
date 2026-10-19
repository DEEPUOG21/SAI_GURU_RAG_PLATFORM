# SaiTech Engineering Guidelines

Synthetic company document · Owner: Engineering · Version 1.0 · Effective 1 January 2026

## Change review

All production code changes require a pull request and at least one approval from a reviewer other than the author. Changes to authentication, authorization, cryptography, or data deletion require a Security reviewer. The author must describe the behavior change and relevant test evidence.

## Testing and delivery

Pull requests must pass linting, type checks, unit tests, and relevant integration tests. Deployments use the CI pipeline and require a rollback plan. Database changes must use versioned migrations. Avoid destructive schema changes until existing callers have migrated.

## Reliability

Every service exposes a health endpoint and structured logs with request IDs. Do not log credentials or customer document contents. Define meaningful latency and error metrics before launch. Keep runbooks close to the service code and update them after incidents.

## API conventions

Public APIs use versioned routes and consistent error objects. Validate all request data and apply authorization in the service that reads the data. Use idempotency keys for operations that could be retried and cause duplicate effects.

## Knowledge assistant architecture

SaiTech's knowledge assistant uses PostgreSQL for both vector search and full-text search. Reciprocal Rank Fusion combines independently ranked candidates. A reranker chooses relevant evidence before answer generation. Answers preserve document titles, section names, and available page numbers.
