import { FlaskConical, Play } from "lucide-react";
import { useEffect, useState } from "react";
import {
  Badge,
  Button,
  date,
  Empty,
  ErrorNotice,
  latency,
  PageHeading,
} from "../components/ui";
import { api } from "../lib/api";
import type { Evaluation } from "../lib/types";

const labels: Record<string, string> = {
  recall_at_k: "Recall@6",
  precision_at_k: "Precision@6",
  mrr: "MRR",
  ndcg: "NDCG",
  faithfulness: "Faithfulness pass rate",
  answer_relevance: "Answer relevance · token F1",
  context_relevance: "Context relevance · labels",
  citation_correctness: "Citation correctness",
};
export function Evaluations() {
  const [runs, setRuns] = useState<Evaluation[]>([]),
    [selected, setSelected] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const active = runs.find((run) => run.id === selected) || runs[0];
  function refresh() {
    return api<Evaluation[]>("/evaluation/results")
      .then(setRuns)
      .catch((e) => setError(e.message));
  }
  useEffect(() => {
    void refresh();
  }, []);
  async function run() {
    setBusy(true);
    setError("");
    try {
      const result = await api<Evaluation>("/evaluation/run", {
        method: "POST",
      });
      setSelected(result.id);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="QUALITY & EVALUATION"
        title="Measure. Learn. Improve."
        description="Run your configured evaluation dataset against your knowledge pipeline."
        action={
          <Button disabled={busy} onClick={() => void run()}>
            <Play size={15} />
            {busy ? "Evaluation running…" : "Run evaluation"}
          </Button>
        }
      />
      <ErrorNotice message={error} />
      <div className="evaluation-note">
        <FlaskConical size={22} />
        <div>
          <strong>Small dataset. Transparent measurements.</strong>
          <p>
            Upload and index the documents covered by your evaluation dataset first. Retrieval
            scores use labeled documents. Generation metrics include clearly
            identified proxies — see the methodology below.
          </p>
        </div>
        <Badge>Configured dataset</Badge>
      </div>
      {busy && (
        <div className="loading">
          <span className="pulse-dot" />
          Running real questions through retrieval, generation, and grounding.
          This can take several minutes.
        </div>
      )}
      {!active ? (
        <section className="panel">
          <Empty
            title="Your first benchmark awaits"
            description="No evaluation results exist yet. Run the dataset to establish a measured baseline; subsequent runs show changes against it."
          />
        </section>
      ) : (
        <>
          <div className="evaluation-toolbar">
            <select
              aria-label="Evaluation run"
              value={active.id}
              onChange={(e) => setSelected(e.target.value)}
            >
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {date(r.created_at)} · {r.id.slice(0, 8)} · {r.status}
                </option>
              ))}
            </select>
            <Badge status={active.status}>{active.status}</Badge>
          </div>
          <ErrorNotice message={active.results.error || ""} />
          <div className="evaluation-grid">
            {Object.entries(labels).map(([key, label]) => {
              const value = active.results.aggregate?.[key],
                delta = active.results.delta?.[key];
              return (
                <section className="metric-card" key={key}>
                  <div className="metric-top">{label}</div>
                  <strong>
                    {value == null ? "—" : `${(value * 100).toFixed(1)}%`}
                  </strong>
                  <span className="metric-note">
                    {delta == null
                      ? "No previous baseline"
                      : `${delta >= 0 ? "+" : ""}${(delta * 100).toFixed(1)} pp vs. previous run`}
                  </span>
                </section>
              );
            })}
          </div>
          <section className="panel mt-6">
            <div className="panel-heading">
              <h2>Case results</h2>
              <span className="muted">
                Avg. latency {latency(active.results.aggregate?.latency_ms)}
              </span>
            </div>
            {active.results.cases?.map((c) => (
              <details className="evaluation-case" key={c.question}>
                <summary>
                  {c.question}
                  <Badge>
                    {(c.metrics.recall_at_k * 100).toFixed(0)}% recall
                  </Badge>
                </summary>
                <div>
                  <h4>Expected answer</h4>
                  <p>{c.expected_answer}</p>
                  <h4>Actual answer</h4>
                  <p className="whitespace-pre-wrap">{c.answer}</p>
                  <small>
                    Latency: {latency(c.metrics.latency_ms)} · Tokens:{" "}
                    {c.token_usage?.total_tokens ?? "not reported"} · Estimated
                    cost:{" "}
                    {c.estimated_cost == null
                      ? "not available"
                      : `$${c.estimated_cost.toFixed(6)}`}
                  </small>
                </div>
              </details>
            ))}
          </section>
          {active.results.methodology && (
            <section className="panel mt-6">
              <div className="panel-heading">
                <h2>How these metrics are calculated</h2>
              </div>
              <dl className="methodology">
                {Object.entries(active.results.methodology).map(
                  ([key, value]) => (
                    <div key={key}>
                      <dt>{key.replaceAll("_", " ")}</dt>
                      <dd>{value}</dd>
                    </div>
                  ),
                )}
              </dl>
            </section>
          )}
        </>
      )}
    </>
  );
}
