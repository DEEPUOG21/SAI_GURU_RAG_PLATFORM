# Sai Guru: measured answer-quality improvement

The [56-question retrieval comparison](RETRIEVAL-2026-10-27.md) separately measures dense, hybrid and reranked retrieval across three repeated rounds, with per-case rankings, latency, paired intervals and limitations. It does not replace the answer-quality experiment below.

## Guardrail verification

The guardrail release adds deterministic policy checkpoints, protected-data masking and checked-output display. Tests live in [test_guardrails.py](../../backend/tests/test_guardrails.py); policy scope and limitations are in [observability](../observability.md#guardrail-policy).

Measured locally on 26 October 2026:

| Check | Recorded result |
| --- | --- |
| Targeted attack fixtures refused | 18 / 18 |
| Legitimate fixtures refused or modified | 0 / 15 |
| Policy-only timing, median / p95 | 0.039 / 0.082 ms across 3,300 checks |
| Normal RAG acceptance checks | 40 / 40 passed |
| Live checks: attacks, history redaction, injected-document exclusion | 6 / 6 passed |
| Disposable database integration tests | 3 passed |
| Frontend tests, including suppression of legacy draft events | 12 passed; lint and build passed |

These attack examples are regression fixtures chosen for the implemented rules, not an independent red-team benchmark. The timing excludes model, network and source-authorization costs. Novel encodings, unsupported identifiers and nuanced attacks remain limitations.

An eight-case synthetic RAG evaluation with guardrails enabled (run `2e410271-6776-43e2-88be-58a78731ae06`) recorded token F1 **0.7212**, citation correctness **0.9375**, recall **1.00**, and mean latency **7.75 seconds**. Answer scores matched the preceding recorded run; its mean latency was **4.14 seconds**. Conditions were not controlled, so these runs do not isolate guardrail overhead or establish a speed improvement. Answers now remain private until checks finish, which intentionally changes when text first appears.

Raw logs, test reports and synthetic live-test records remain in ignored `.local/deployment/`.

## Result

On a fixed eight-question synthetic company-policy benchmark, answer token-set F1 increased from **0.4745 to 0.7135** and exact citation-label matching increased from **81.25% to 93.75%**, while Recall@6 and MRR remained **1.00**.

These are recorded application evaluations, not RAGAS or LangSmith results. The evidence supports a small benchmark improvement, not a general accuracy guarantee.

## Evidence chain

- [Benchmark questions and expected answers](../../data/demo/evaluation.json): eight questions spanning eight synthetic documents.
- [Before results](before.json): run `1f983fc4-01c6-4a03-afdb-d075808b8296`, 22 October 2026.
- [After results](after.json): run `5d8a2e72-9262-4c9c-abc1-f62183cb6053`, 23 October 2026.
- [Implementation change](https://github.com/DEEPUOG21/SAI_GURU_RAG_PLATFORM/commit/2bef46c933d37a773b1f7b3a6d5d0f9bff1777b2): constrained generation to the question asked and strengthened the grounding check against invented exceptions, guarantees, and motives.
- [Metric implementation](../../backend/app/evaluation/metrics.py) and [evaluation runner](../../backend/app/evaluation/service.py).

The exported JSON includes every question, reference answer, generated answer, per-case metric, and aggregate. Private traces and infrastructure identifiers are excluded. Each export records the SHA-256 digest of its original private result file for provenance; a hash alone is not independent attestation. Export validation confirmed identical question order and that all aggregate values equal their eight per-case means.

## Before and after

| Measurement | Before | After | Change |
|---|---:|---:|---:|
| Answer relevance: token-set F1 | 0.4745 | 0.7135 | +0.2391 |
| Exact citation document/section match | 81.25% | 93.75% | +12.50 percentage points |
| Recall@6 | 100% | 100% | Maintained |
| MRR | 1.00 | 1.00 | Maintained |
| NDCG | 1.00 | 1.00 | Maintained |
| Precision@6 | 16.67% | 16.67% | Unchanged |
| Context label relevance | 47.92% | 47.92% | Unchanged |
| Grounding judge pass rate | 100% | 100% | Judge missed the original error |
| Mean query latency | 13.30 s | 3.60 s | Observed; uncontrolled comparison |

Token F1 is lexical overlap against reference answers, not semantic accuracy. Citation matching compares returned document/section labels to the expected label. Precision@6 divides by six even though each case has only one labeled relevant document. The remaining citation mismatch is a valid corroborating remote-work citation for internet reimbursement that is absent from the single expected label.

## Concrete failure found and corrected

**Question:** How many annual leave days do full-time SaiTech employees receive?

**Before:** The answer correctly stated 24 working days per year and monthly accrual, but also claimed: “The number of annual leave days for full-time employees is fixed at 24 working days, regardless of the time of year they join.” The source does not support that guarantee.

**After:** “Full-time SaiTech employees receive 24 working days of paid annual leave per calendar year [Source 1].”

The fix made factual answers concise, limited them to the requested information, and explicitly prohibited invented partial-year guarantees and explanations. Manual review caught the failure that the automated grounding judge had accepted. All eight after-run answers were reviewed; this particular unsupported claim was absent.

## How to inspect or repeat

1. Compare corresponding cases in `before.json` and `after.json`; verify claims against the documents in `data/demo/`.
2. Inspect the linked commit to see the exact generation and grounding prompt changes. Retrieval labels were not changed to inflate scores.
3. In the deployed app, sign in as an authorized administrator, open **Evaluations**, and select the recorded runs. The page displays metrics, cases, and methodology.
4. To run a fresh measurement, index the same eight documents and select **Run evaluation**. The backend uses `data/demo/evaluation.json` unless a private `data/evaluation.json` override is configured. Preserve model/settings, corpus, and dataset when comparing runs.

Only one run per condition is included here. Model responses vary. A stronger future experiment would repeat each condition, use a separate held-out dataset, and independently annotate answer correctness. The observed latency reduction is not claimed as a controlled performance improvement: hosting wake-up, provider load, caching, and shorter output can affect it.

## Resume-ready wording

> Evaluated and refined a deployed RAG assistant on an 8-question synthetic policy benchmark, increasing answer token F1 from 0.474 to 0.714 and exact citation matching from 81.25% to 93.75%, while maintaining 100% Recall@6.

> Diagnosed an unsupported leave-policy claim missed by the automated grounding judge; tightened generation and evidence-checking prompts, then verified its removal through before/after answer review.

**Interview explanation:** “I built a fixed benchmark with expected documents, sections, and answers. I found that retrieval worked but generation added unsupported details. I constrained the answer prompt and strengthened grounding instructions, reran the same questions, and saved the per-case outputs. The gains are on a small synthetic benchmark; I do not claim production-wide accuracy or a RAGAS score.”
