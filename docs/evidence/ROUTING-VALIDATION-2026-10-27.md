# Fresh routing validation — 2026-10-27

## Result

The fresh answer-quality run is **inconclusive**. The first planned case stopped on an HTTP 429 from the configured Cloudflare Workers AI endpoint. The same trace recorded 429 failures from the intent router, dense retrieval, reranker, and answer generation. No fresh-answer quality score was produced, and the run was not retried or switched to another model.

The private checkpoint is `.local/deployment/routing-validation-run.json`. It contains scoped source IDs and provider diagnostics and is intentionally excluded from the repository.

## Frozen validation set

`data/demo/routing-validation.json` contains 30 new phrasings: 20 source-answerable, 5 absent facts, and 5 follow-ups. It uses the existing eight synthetic documents. The set was created after the routing implementation and before model inference; it tests fresh phrasings, not an unseen corpus or independently authored benchmark. Its planned coding-agent review rubric is in the dataset. The exact input SHA-256 is recorded in the private checkpoint.

Because inference stopped on the provider error, none of these cases is presented as a completed answer evaluation. Do not cite a routing accuracy or quality improvement from this run.

## Local verification

- Full backend suite: 268 passed, 2 skipped, 1 integration test deselected.
- Focused source-intent and HTTP 429 fallback suite: 13 passed.
- The HTTP 429 integration failure is retained in the private checkpoint; this report records the provider status without publishing scoped source IDs or response payloads.

## Remaining validation

Rerun the frozen set after the free inference endpoint accepts requests. Then review fresh answers and run live document-injection and bounded HTTP-load checks. These results must remain separate from the earlier 60-case tuning/regression set.
