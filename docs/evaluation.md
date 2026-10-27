# Evaluation and regression


The approved dataset in `data/demo/evaluation.json` contains eight synthetic policy questions, reference answers, expected document filenames and citation sections. A private dataset may be supplied through `data/evaluation.json`. These cases test the supplied documents; they are not a general accuracy benchmark. See [recorded evidence](evidence/README.md).

Seed and index the demo documents, sign in as MANAGER or ADMIN, and select **Run evaluation**. Each question executes the real configured pipeline with the user's current access. Results are persisted in `evaluations`, including actual answers, citations, measured latency, available token usage and node traces. No evaluation numbers are present until a run produces them.

## Retrieval metrics

The unit of relevance is a unique document, because the dataset labels documents rather than hardcoded chunk UUIDs. Candidate document names are deduplicated in rank order. K is 6.

- **Recall@6:** relevant retrieved documents / total expected documents.
- **Precision@6:** relevant retrieved documents / 6. The denominator stays six even if fewer candidates are returned. A case with only one relevant expected document has maximum Precision@6 of 1/6; this is intentional.
- **MRR:** reciprocal of the first relevant document rank, or zero.
- **NDCG:** binary relevance DCG with log2 discount divided by ideal DCG.

`tests/test_evaluation.py` fixes a known ranked fixture and asserts exact expected formulas, including duplicate handling and empty-result penalties. `tests/test_retrieval.py` verifies RRF scoring and metadata preservation. The native integration test verifies that actual vector/full-text results carry real scores after indexing.

## Generation metrics: explicit limitations

| Displayed metric | Implemented method | Interpretation |
|---|---|---|
| Faithfulness pass rate | 1 when the answer passed the grounding check, otherwise 0; averaged over cases | LLM-judged binary pass rate. In extractive mode it reflects verbatim source quoting. It is not claim-level RAGAS faithfulness or a calibrated semantic score. |
| Answer relevance · token F1 | Set-based lexical F1 between answer and expected-answer tokens | A transparent lexical proxy; a valid paraphrase can score poorly. |
| Context relevance · labels | Fraction of candidate chunks from expected documents | Label-based retrieval-context proxy, not semantic LLM assessment. |
| Citation correctness | Fraction of returned citations matching an expected document **and section** | Dataset-level citation match; complements, but does not replace, claim-level verification. |

These methods are intentionally visible in both the UI and API results. There are no fabricated semantic scores. A stronger study should add multiple human-reviewed questions per policy, expected chunk spans, adversarial cases, answerable/unanswerable labels, and independent claim-level assessment.

## System measurements

Latency uses elapsed monotonic time for the actual pipeline. Token totals include all generation, grounding and regeneration calls. They are reported only when every executed model call provides complete usage; if any report is missing, both usage and cost are null/“not reported”. No tokenizer estimate or partial sum is mislabeled as measured total usage. Estimated cost uses configured USD-per-million rates. Local inference rates are zero, but CPU/electricity/hosting opportunity costs are not modeled.

## Regression comparison

A completed run compares aggregate metrics with the previous completed run for the same user, tenant and dataset version. The API returns a baseline ID and deltas; UI percentages show percentage-point differences. Changing the corpus, model or generation mode can affect comparability, so record those settings with experiments and compare like-for-like. Failed runs retain partial completed cases and an error, and must not be treated as a complete benchmark.

The API currently runs the small dataset within the request with a ten-minute overall bound and one start per user/minute. There is no long-running evaluation worker or automatic release quality threshold. CI enforces deterministic regression tests and the real database integration scenario; evaluation scores are not assumed to pass an invented threshold.

## Frozen retrieval comparison

`data/demo/retrieval-holdout.json` is a separate, 56-question diagnostic set with document-and-section relevance labels: 48 within-document questions (one requires two sections) and eight cross-document questions. It has no exact question overlap with the eight tuning questions. It was authored from the same known synthetic documents and frozen by SHA-256 before measurement. Dataset fingerprints use UTF-8 text with CRLF normalized to LF for consistent Git checkouts; the original run retains both its pre-measurement Windows-file digest and normalized digest. It is held out from tuning for this comparison, not independently annotated or an unseen-corpus test. Some underlying facts are shared with earlier tests.

With the existing private runtime configuration and the same embedding/reranking models used for indexing, run:

```powershell
python scripts/benchmark_retrieval.py --repeats 3
```

The command requires a non-owner runtime database role, enforces read-only transactions, binds the configured seed user's access scope, and checks all eight indexed document hashes and every section label before inference. It verifies the indexed chunk snapshot again at completion. No documents, conversations or evaluations are written to the database. Results checkpoint to ignored `.local/deployment/retrieval-ablation.json`; failures remain explicit, without substituting fallback rankings.

For each question/repeat, dense-only, hybrid RRF, and hybrid RRF plus reranking share the same candidate lists (20 per retriever, RRF constant 60, final six chunks). Question order is shuffled deterministically per round. Metrics score exact labeled sections on the actual top six chunks; duplicate sections earn no additional credit. Section Hit@1, Recall@6, MRR@6 and NDCG@6 distinguish useful evidence ranking from merely retrieving the correct document. Document Recall@6 is retained for comparison with the older metric. Labels identify required sections; other useful corroborating evidence is not exhaustively judged.

Paired score differences include wins/ties/losses and exploratory 95% percentile-bootstrap intervals over question clusters, averaging matched repeats first. Repeating the same question does not triple the independent sample size. Intervals do not measure annotation uncertainty or establish performance beyond this small corpus.

Latency p50/p95 uses measured component durations in sequential production order: dense; dense plus lexical/fusion; plus reranking. Shared retrieval work is measured once per question/repeat. These are component-derived timings, not independently executed end-to-end requests; they exclude authorization setup, routing, generation and the client-to-API network. Provider failures count separately. This retrieval study does not measure answer correctness, unknown-answer handling, conversational rewriting or attack resistance.

To prepare a LangSmith comparison from a completed mode:

```powershell
python scripts/export_langsmith.py .local/deployment/retrieval-ablation.json --retrieval-mode dense --name sai-guru-retrieval-dense --output .local/deployment/retrieval-dense-preview.json
```

Repeat with `hybrid` and `hybrid_reranked`, using distinct experiment names and output files. Preview is local by default; `--upload` sends the synthetic questions, source labels, ranked document/section names and scores to the configured LangSmith workspace. Every mode uses the same 56 reference examples. Each experiment contains one case per question with metrics averaged over repeats, all repeated rankings retained, and reconstructed display timestamps explicitly labeled as imported. LangSmith is the comparison viewer; the application computed these metrics.
