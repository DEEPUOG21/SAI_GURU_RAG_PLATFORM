# Retrieval comparison: 56 questions, three repeated rounds

Measured on 27 October 2026 using the existing eight-document synthetic corpus, 49 indexed chunks, and the production retrieval implementations. The frozen diagnostic questions were not used to change prompts, models or ranking parameters during this experiment.

The questions label 35 distinct source sections. Rankings were identical across all three repeats for each question/mode; repeats therefore provide repeated timing measurements, not additional independent quality evidence.

## Observed results

| Measurement | Dense only | Hybrid RRF | Hybrid RRF + reranking |
| --- | ---: | ---: | ---: |
| Section Hit@1 | 85.71% | 89.29% | **92.86%** |
| Section Recall@6 | 98.21% | **100%** | **100%** |
| Section MRR@6 | 0.9009 | 0.9375 | **0.9515** |
| Section NDCG@6 | 0.9158 | 0.9487 | **0.9601** |
| Document Recall@6 | 100% | 100% | 100% |
| Component-derived latency p50 | 789 ms | 855 ms | 1,747 ms |
| Component-derived latency p95 | 1,224 ms | 1,334 ms | 2,970 ms |
| Completed rankings / planned rankings | 168 / 168 | 168 / 168 | 168 / 168 |

The reranked pipeline's observed top-ranked section hit rate is **7.14 percentage points higher** than dense-only search. MRR improves by **0.0506**. Hybrid retrieval recovers one question's required evidence that dense-only misses within six chunks. All modes already achieve perfect document recall, which is why the more specific section labels are useful.

Reranking has a measurable cost: median retrieval-component latency rises from 789 ms for dense-only to 1,747 ms for the full pipeline. No latency improvement or answer-generation improvement is claimed.

## Paired uncertainty and regressions

Comparing dense-only against hybrid plus reranking, after averaging the three repeats for each of the 56 questions:

| Measurement | Mean difference | Exploratory 95% bootstrap interval | Questions improved / tied / worsened |
| --- | ---: | ---: | ---: |
| Section Hit@1 | +7.14 pp | −1.79 to +16.07 pp | 6 / 48 / 2 |
| Section Recall@6 | +1.79 pp | 0.00 to +5.36 pp | 1 / 55 / 0 |
| Section MRR@6 | +0.0506 | −0.0152 to +0.1185 | 7 / 46 / 3 |
| Section NDCG@6 | +0.0443 | −0.0043 to +0.0954 | 8 / 45 / 3 |

The Hit@1, MRR and NDCG intervals include zero. This is an observed improvement on this diagnostic set, not statistically conclusive evidence of a population-wide improvement. The regressions are retained in the raw results. Repeated measurements do not turn 56 questions into 168 independent relevance judgments.

## Evidence and reproduction

- [Frozen questions and required source sections](../../data/demo/retrieval-holdout.json): 48 within-document questions, including one requiring two sections, and eight cross-document questions. Labels were authored against source sections and validated against the indexed corpus before inference.
- [All measured rankings, timings, configurations, hashes and comparisons](retrieval-ablation.json): 504 rankings, including failures if any; this run had zero. Actual top-six document/section names are retained for every question, mode and repeat.
- Original pre-measurement Windows-file SHA-256 (CRLF): `e13313ae2f70aeb98fd8c2478986666cd268a76a4d6873fb4d2086068cdb7500`. The recorded run and imported LangSmith dataset retain this original identity.
- Checkout-independent LF-normalized SHA-256: `0b2f22288143a5f0d6f531d6d83f5199e97b2a27c8bb14aa8b6930e4c8cc37bb`. Git normalizes line endings; the runner now fingerprints normalized UTF-8 text, and the recorded evidence retains both digests. Question content and all measurements are unchanged.
- The result records the source-file hashes and indexed chunk snapshot digest. The corpus snapshot was rechecked unchanged after measurement.
- Backend regression verification: 244 passed, two skipped, one integration test deselected. Focused metric, retrieval and export tests: 26 passed.
- [Reusable command and metric definitions](../evaluation.md#frozen-retrieval-comparison). The runner uses a non-owner runtime role, read-only transactions and the configured user's existing document permissions.

Models: Cloudflare `@cf/baai/bge-small-en-v1.5` embeddings and `@cf/baai/bge-reranker-base` reranking. Each retriever returns up to 20 candidates, RRF uses constant 60, and the final cutoff is six actual chunks. Candidate lists are shared between ablations for each query/repeat; no retries or silent fallback rankings are used.

The benchmark is an author-generated, held-out-from-tuning diagnostic set over an already known synthetic corpus. It contains no exact duplicate of the eight tuning questions, but some underlying facts overlap with earlier tests. It is not independently annotated, and labels are not exhaustive judgments of every potentially useful section. No new answer generation is performed. This study does not establish answer correctness, unknown-answer behavior, conversational rewriting, real-world retrieval accuracy or security robustness.

Latency is calculated from measured, sequential component durations shared by the ablations. It excludes authentication setup, routing, LLM generation and the client-to-API network, and should not be presented as end-to-end response latency. Bootstrap intervals use 2,000 paired question-cluster resamples and do not account for annotation uncertainty or multiple comparisons.

## Resume wording supported by this experiment

> Evaluated dense, hybrid and reranked retrieval on 56 labeled synthetic queries across three repeated rounds (504 rankings), improving observed section Hit@1 from 85.71% to 92.86% and MRR@6 from 0.9009 to 0.9515, while raising section Recall@6 to 100%.

In an interview, explain that the gains are benchmark-specific, the confidence intervals remain wide, and reranking increases retrieval latency.

## LangSmith comparison

The three imported experiments are available in the existing [LangSmith retrieval dataset](https://smith.langchain.com/o/2a4a8185-3a71-4629-8b30-a89e91d915c3/a/-/datasets/e130e376-ebe3-40f0-b0ff-b2a3e84b0f2b), requiring workspace access:

- `sai-guru-retrieval-dense-oct27-v1`
- `sai-guru-retrieval-hybrid-oct27-v1`
- `sai-guru-retrieval-hybrid_reranked-oct27-v1`

Readback verified 56 runs per experiment, zero recorded import-run errors, the same 56 reference examples in all three, and quality scores agreeing with local results within the service's rounded feedback-stat precision. Each run retains all three measured rankings and repeat-averaged metrics. Timelines are reconstructed from component durations and explicitly marked imported; these are not LangSmith-native rescoring or live generation traces.
