# Free hosted inference with Cloudflare Workers AI

This configuration uses one Cloudflare account for chat, embeddings and reranking. It needs no inference container or additional Python dependencies. Keep the account on **Workers Free**. Cloudflare documents 10,000 Neurons per day; requests fail when the free quota is exhausted. Paid accounts can incur overage charges, so verify the plan before configuring production. Availability and quotas can change.

Documentation checked 2026-10-18:

- [Pricing and free quota](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- [Chat and embedding API compatibility](https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/)
- [Reranker API](https://developers.cloudflare.com/workers-ai/models/bge-reranker-base/)

## Configuration

Sign in to Cloudflare, select the intended account, and create an API token scoped to Workers AI access for that account. Store it only in Render's server environment, never in Git, frontend variables, or chat. No domain transfer, Worker deployment, or change to Vercel hosting is required.

Set the following environment values on the existing Render API service, replacing ACCOUNT_ID and the token placeholders:

```dotenv
EMBEDDING_PROVIDER=http
EMBEDDING_URL=https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/v1/embeddings
EMBEDDING_MODEL=@cf/baai/bge-small-en-v1.5
EMBEDDING_DIMENSIONS=384
RERANKER_PROVIDER=cloudflare
RERANKER_URL=https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/run/@cf/baai/bge-reranker-base
RERANKER_MODEL=@cf/baai/bge-reranker-base
INFERENCE_API_KEY=YOUR_PRIVATE_WORKERS_AI_TOKEN
LLM_URL=https://api.cloudflare.com/client/v4/accounts/ACCOUNT_ID/ai/v1
LLM_MODEL=@cf/meta/llama-3.1-8b-instruct-fp8-fast
LLM_API_KEY=YOUR_PRIVATE_WORKERS_AI_TOKEN
GENERATION_MODE=llm
GENERAL_FALLBACK_ENABLED=true
GROUNDING_ACTION=regenerate
QUERY_TIMEOUT_SECONDS=300
LLM_INPUT_COST_PER_MILLION=0
LLM_OUTPUT_COST_PER_MILLION=0
```

Deploy the backend version containing `RERANKER_PROVIDER=cloudflare` support before selecting it. Keep database, JWT and CORS settings as configured. Zero cost estimates above assume Workers Free; they are not a billing cap for a paid account.

## Verification before declaring the app ready

1. Check a direct chat stream, JSON-mode response, 384-dimensional embedding, and reranker request with the configured token. Local mocked contract tests do not prove live API compatibility or model quality.
2. Upload a temporary text document, process it, and require COMPLETED status.
3. Verify a greeting, contextual follow-up, unknown/general topic, and a grounded document question with correct citations. Treat SSE error events as failures even when HTTP status is 200.
4. Delete the temporary test records and inspect provider usage.

Reindex documents when changing embedding providers, even when their model names and dimensions match: preprocessing may differ. The currently deployed database had zero indexed documents during the last verification. Do not automatically delete or reindex unrelated user data.

The app can make multiple model requests per chat for rewriting, answering and grounding; the daily quota is shared across those calls and ingestion. This is a limited free deployment, not unlimited production capacity. Provider failures remain explicit; the application must not claim successful answers when quota is exhausted.
