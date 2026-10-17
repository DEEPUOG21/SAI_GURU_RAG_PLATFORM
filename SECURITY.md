# Security

Do not publish passwords, tokens, database URLs containing credentials, uploaded company documents, or model caches in issues or commits. Use the repository's private vulnerability reporting feature when enabled; otherwise contact the repository owner privately before disclosing sensitive details.

The API must use a non-owner database role. Migration credentials belong only in the provisioning environment. The browser must never receive database credentials or inference keys.

See [the security audit](docs/SECURITY-AUDIT.md), [hardening results](docs/HARDENING-RESULTS.md), and [release readiness](docs/RELEASE-READINESS.md). Historical test results are evidence from their recorded runs, not a guarantee that the current dependency ecosystem is vulnerability-free.
