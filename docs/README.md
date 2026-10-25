# Documentation

For the current free hosted model setup, see [Cloudflare inference configuration](guides/FREE-INFERENCE.md).
For workflow orchestration and optional hosted experiment comparison, see [LangGraph and LangSmith](guides/LANGGRAPH-LANGSMITH.md).

| Folder | Contents |
| --- | --- |
| [guides](guides/SETUP.md) | Setup, local development, deployment and troubleshooting |
| [architecture](architecture/ARCHITECTURE.md) | System design, RAG pipeline and evaluation methodology |
| [security](security/HARDENING-RESULTS.md) | Security review, hardening and audit reproduction |
| [operations](operations/RELEASE-READINESS.md) | Release requirements and verification history |
| audit/ | Historical machine-readable verification evidence |

The single project checkout is the repository root. Private workspace archives and raw scans live in ignored `.local/`. Runtime dependencies, databases, model caches and credentials are ignored and remain at their configured paths.

User-approved synthetic knowledge documents and the eight-question benchmark are in `data/demo/`. Recorded before/after results are in [evaluation evidence](evaluation-evidence/README.md). See [evaluation configuration](../data/README.md) before running benchmarks.
