# LangGraph integration validation — 25 October 2026

Validation covers the pending LangGraph/LangSmith integration against real Supabase and Cloudflare services, with database TLS certificate verification enabled.

| Check | Result |
| --- | --- |
| Backend regression suite | 178 passed; three database tests run separately below |
| Disposable PostgreSQL integration suite | 3 passed: real ingestion/query flow, runtime-role isolation, retention |
| Frontend unit tests | 7 passed |
| Frontend lint and production build | Passed |
| Local LangGraph API acceptance suite | 40 passed, zero failed |
| Additional local API checks | Login, anonymous-access denial, CORS, invalid uploads, ingestion, grounded retrieval, general knowledge and follow-ups passed |
| Browser against local LangGraph backend | Login and streamed document answer with citation verified |
| LangSmith delivery | 100 recent spans inspected; zero recorded errors; inputs/outputs hidden |
| Repository layout and configured-secret checks | Passed |

Temporary API test documents and conversations were cleaned up. Database integration tests used a separate local `sai_guru_test` database. Live acceptance checks used synthetic knowledge documents; they do not establish behavior on arbitrary company data.

The earlier hosted eight-case benchmark completed on 25 October with displayed token F1 72.1%, citation correctness 93.8%, recall 100%, and mean latency 3.36 seconds. That run preceded deployment of this integration and must not be described as a LangGraph performance improvement. Token F1 is a lexical proxy; the grounding pass rate is judged by a fallible model. See the evidence README for methodology.

This is functional regression evidence, not a penetration test, cross-browser certification or sustained load benchmark. Detailed private logs are retained under ignored `.local/deployment/`.
