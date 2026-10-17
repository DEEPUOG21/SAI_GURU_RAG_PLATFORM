# Documentation

| Folder | Contents |
| --- | --- |
| [guides](guides/SETUP.md) | Setup, local development, deployment and troubleshooting |
| [architecture](architecture/ARCHITECTURE.md) | System design, RAG pipeline and evaluation methodology |
| [security](security/HARDENING-RESULTS.md) | Security review, hardening and audit reproduction |
| [operations](operations/RELEASE-READINESS.md) | Release requirements and verification history |
| audit/ | Historical machine-readable verification evidence |

The single project checkout is the repository root. Private workspace archives and raw scans live in ignored `.local/`. Runtime dependencies, databases, model caches and credentials are ignored and remain at their configured paths.

Demo documents and synthetic employee seeding have been removed. Existing databases are not erased by this source cleanup. Historical audit reports describe the fixtures present when those checks ran. New installations create an admin account, then accept your own uploads. See [evaluation configuration](../data/README.md) before running benchmarks.
