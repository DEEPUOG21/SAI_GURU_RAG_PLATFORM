# Security

Do not publish passwords, tokens, database URLs containing credentials, uploaded company documents, or model caches in issues or commits. Use the repository's private vulnerability reporting feature when enabled; otherwise contact the repository owner privately before disclosing sensitive details.

The API must use a non-owner database role. Migration credentials belong only in the provisioning environment. The browser must never receive database credentials or inference keys.

Access boundaries are described in [architecture](docs/architecture.md), deployment requirements in [deployment](docs/deployment.md), and measured checks in [evaluation evidence](docs/evidence/README.md). Historical raw audits are archived privately. Recorded checks do not guarantee that current dependencies are vulnerability-free.
