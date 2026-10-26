# Streaming and capacity verification

## Changes

The browser now rejects a terminal `done` event that has no preceding `final` answer or explicit `error`. After a valid terminal event, it releases the response reader immediately rather than waiting for the transport to close. Premature transport closure still produces an explicit retry message. No automatic question resubmission is performed.

Backend failure diagnostics include the exception class and query ID, without recording exception messages, prompts or credentials. Client-disconnect detection is logged separately.

These changes address reproducible protocol-handling gaps. They do not establish the cause of the single incomplete production response observed on 25 October; the full acceptance rerun subsequently passed 40/40.

## Verification

- Frontend: 11 tests passed, including truncated transport, `done` without an answer, and final/error completion while the transport remains open. ESLint and production build passed.
- Backend: 11 targeted streaming, provider-failure, database-readiness and admission-control tests passed.
- Existing deployed release, bounded live concurrency check: four simultaneous policy requests produced two completed, grounded answers and two HTTP 429 responses with `Retry-After: 5`. A subsequent request completed normally. Accepted requests took approximately 3.79 and 4.18 seconds; recovery took 2.99 seconds. Test conversations were deleted.

This is a four-request capacity smoke test, not a sustained load benchmark. Provider/database outage cases were simulated in tests; production dependencies were not deliberately disabled.

## Remaining verification

Mobile, multiple browser engines and the full browser role matrix remain unverified. No browser was connected to the automation session on 26 October. This patch's deployment and browser verification must be confirmed separately from the already deployed LangGraph release.
