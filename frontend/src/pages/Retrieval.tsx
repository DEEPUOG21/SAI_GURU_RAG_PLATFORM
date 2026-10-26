import { ArrowDown, Braces, Search } from "lucide-react";
import { useEffect, useState } from "react";
import {
  Badge,
  Button,
  Empty,
  ErrorNotice,
  latency,
  PageHeading,
  SourceModal,
} from "../components/ui";
import { api } from "../lib/api";
import type { DebugQuery, Source } from "../lib/types";

export function Retrieval({ queryId }: { queryId: string }) {
  const [id, setId] = useState(queryId),
    [query, setQuery] = useState<DebugQuery | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [source, setSource] = useState<Source | null>(null);
  async function load(value: string) {
    if (!value.trim()) return;
    setBusy(true);
    setError("");
    setQuery(null);
    try {
      setQuery(
        await api<DebugQuery>(
          `/retrieval/debug/${encodeURIComponent(value.trim())}`,
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (queryId) {
      setId(queryId);
      void load(queryId);
    }
  }, [queryId]);
  const score = (value: number | null | undefined) =>
    value == null ? "—" : value.toFixed(4);
  return (
    <>
      <PageHeading
        eyebrow="RETRIEVAL LAB"
        title="Understand every answer."
        description="Inspect the actual route, evidence, scores, and decisions behind a query."
      />
      <form
        className="debug-search"
        onSubmit={(e) => {
          e.preventDefault();
          void load(id);
        }}
      >
        <Search size={19} />
        <input
          aria-label="Query ID"
          placeholder="Paste a query ID, or inspect a question from the dashboard"
          value={id}
          onChange={(e) => setId(e.target.value)}
        />
        <Button disabled={busy || !id.trim()}>
          {busy ? "Inspecting…" : "Inspect query"}
        </Button>
      </form>
      <ErrorNotice message={error} />
      {!query && !busy && (
        <section className="panel">
          <Empty
            title="Follow the evidence"
            description="Run a question in the assistant, then select Inspect retrieval. Every step below will come from the real backend execution trace."
          />
          <div className="pipeline-preview">
            {[
              "Classify",
              "Rewrite",
              "Retrieve",
              "Fuse",
              "Rerank",
              "Generate",
              "Verify",
            ].map((label, i) => (
              <span key={label}>
                {i > 0 && <ArrowDown size={14} />}
                <Badge>{label}</Badge>
              </span>
            ))}
          </div>
        </section>
      )}
      {query && (
        <>
          <div className="query-summary panel">
            <div>
              <span className="eyebrow">ORIGINAL QUESTION</span>
              <h2>{query.question}</h2>
              <p>Rewritten: {query.rewritten_query || "Unavailable"}</p>
            </div>
            <div className="source-meta">
              <Badge>{query.route}</Badge>
              <Badge status={query.status}>{query.status}</Badge>
              <span>{latency(query.latency_ms)}</span>
            </div>
          </div>
          <div className="debug-columns">
            <section className="panel">
              <div className="panel-heading">
                <h2>Guardrail decisions</h2>
              </div>
              {query.trace.filter((step) => step.node.startsWith("guardrail_"))
                .length === 0 ? (
                <p className="muted">
                  This historical run has no recorded guardrail decisions.
                </p>
              ) : (
                query.trace
                  .filter((step) => step.node.startsWith("guardrail_"))
                  .map((step, i) => (
                    <div key={`guard-${i}`}>
                      <strong>{step.node.replaceAll("_", " ")}</strong>
                      <pre>{JSON.stringify(step.output, null, 2)}</pre>
                    </div>
                  ))
              )}
              <div className="panel-heading">
                <h2>Execution trace</h2>
                <Braces size={18} />
              </div>
              <div className="trace-list">
                {query.trace.map((step, i) => (
                  <div className="trace-step" key={`${step.node}-${i}`}>
                    <span className={`step-dot ${step.status}`}>
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <div className="trace-title">
                        <strong>{step.node.replaceAll("_", " ")}</strong>
                        <Badge
                          status={
                            step.status === "completed"
                              ? "COMPLETED"
                              : step.status === "failed"
                                ? "FAILED"
                                : ""
                          }
                        >
                          {step.status}
                        </Badge>
                      </div>
                      {step.latency_ms != null && (
                        <small>
                          {step.latency_ms.toFixed(1)} ms · {step.attempts}{" "}
                          attempt(s)
                        </small>
                      )}
                      {step.output != null && (
                        <pre>
                          {typeof step.output === "string"
                            ? step.output
                            : JSON.stringify(step.output, null, 2)}
                        </pre>
                      )}
                      {step.error && (
                        <span className="error-text">{step.error}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
            <div>
              <section className="panel mb-5">
                <div className="panel-heading">
                  <h2>Generation details</h2>
                </div>
                <dl className="detail-list">
                  <div>
                    <dt>Grounding</dt>
                    <dd>
                      <Badge status={query.grounding}>{query.grounding}</Badge>
                    </dd>
                  </div>
                  <div>
                    <dt>Total latency</dt>
                    <dd>{latency(query.latency_ms)}</dd>
                  </div>
                  <div>
                    <dt>Token usage</dt>
                    <dd>{query.token_usage?.total_tokens ?? "Not reported"}</dd>
                  </div>
                  <div>
                    <dt>Estimated cost (USD)</dt>
                    <dd>
                      {query.estimated_cost == null
                        ? "Not available"
                        : `$${query.estimated_cost.toFixed(6)}`}
                    </dd>
                  </div>
                </dl>
                <p className="footnote">
                  Cost uses configured provider rates. Token totals include
                  generation and grounding calls when reported.
                </p>
              </section>
              <section className="panel">
                <div className="panel-heading">
                  <h2>Final answer</h2>
                </div>
                <p className="final-answer">
                  {query.answer || query.error || "No completed answer."}
                </p>
              </section>
            </div>
          </div>
          <section className="panel mt-6">
            <div className="panel-heading">
              <div>
                <h2>Retrieved evidence</h2>
                <p>
                  Final candidates, with scores from each actual retrieval stage
                </p>
              </div>
              <Badge>{query.candidates.length} chunks</Badge>
            </div>
            {query.candidates.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Source / chunk</th>
                      <th>Page / section</th>
                      <th>Dense</th>
                      <th>Lexical</th>
                      <th>RRF</th>
                      <th>Reranker</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.candidates.map((c, i) => (
                      <tr key={c.chunk_id || i}>
                        <td>
                          <button
                            className="inline-link"
                            onClick={() =>
                              setSource({ ...c, label: `Candidate ${i + 1}` })
                            }
                          >
                            {c.document}
                          </button>
                          <small className="mono">{c.chunk_id}</small>
                        </td>
                        <td>
                          {c.page ?? "—"} / {c.section}
                        </td>
                        <td>{score(c.dense_score)}</td>
                        <td>{score(c.lexical_score)}</td>
                        <td>{score(c.rrf_score)}</td>
                        <td>{score(c.reranker_score)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty
                title="No document candidates"
                description="The route may be DIRECT or SQL, retrieval may have found no sources, or the query may have failed before persistence."
              />
            )}
          </section>
          <p className="page-footnote mono">
            Request ID: {query.request_id} · Query ID: {query.id}
          </p>
        </>
      )}
      <SourceModal source={source} onClose={() => setSource(null)} />
    </>
  );
}
