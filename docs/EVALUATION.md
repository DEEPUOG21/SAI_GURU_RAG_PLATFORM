# Evaluation and regression

The dataset in `data/evaluation.json` contains three synthetic questions, reference answers, expected document filenames and expected citation sections. It covers annual leave, expense-submission deadlines and SEV1 acknowledgement targets. These cases test the provided SaiTech documents only; they are not a general benchmark.

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
