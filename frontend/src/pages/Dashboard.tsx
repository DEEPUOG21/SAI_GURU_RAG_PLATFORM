import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  Clock3,
  FileText,
  Layers3,
  MessageSquare,
  Plus,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  Badge,
  Button,
  CardLink,
  date,
  Empty,
  ErrorNotice,
  latency,
  Loading,
  PageHeading,
} from "../components/ui";
import { api } from "../lib/api";
import type { Dashboard as DashboardData, User } from "../lib/types";

export function Dashboard({
  user,
  navigate,
  signIn,
  inspect,
}: {
  user: User | null;
  navigate: (page: string) => void;
  signIn: () => void;
  inspect: (id: string) => void;
}) {
  const [data, setData] = useState<DashboardData | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false);
  useEffect(() => {
    let active = true;
    if (user) {
      setLoading(true);
      api<DashboardData>("/dashboard")
        .then((value) => {
          if (active) setData(value);
        })
        .catch((e) => {
          if (active) setError(e.message);
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }
    return () => {
      active = false;
    };
  }, [user]);
  const stats = [
    {
      label: "Documents indexed",
      value: data?.documents_indexed,
      icon: FileText,
      note: "Accessible knowledge sources",
    },
    {
      label: "Total queries",
      value: data?.total_queries,
      icon: MessageSquare,
      note: "Questions from your account",
    },
    {
      label: "Successful queries",
      value: data?.successful_queries,
      icon: CheckCircle2,
      note: "Completed without system errors",
    },
    {
      label: "Avg. response time",
      value: data ? latency(data.average_latency_ms) : undefined,
      icon: Clock3,
      note: "Measured end-to-end latency",
    },
  ];
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE OVERVIEW"
        title="Knowledge, connected."
        description="A clear view of what your team knows — and what comes next."
        action={
          <Button onClick={() => (user ? navigate("documents") : signIn())}>
            <Plus size={16} />
            Add documents
          </Button>
        }
      />
      <ErrorNotice message={error} />
      <section className="hero-card">
        <div className="hero-copy">
          <div className="hero-label">
            <span className="pulse-dot" />
            YOUR KNOWLEDGE. WITH CONTEXT.
          </div>
          <h2>
            From information
            <br />
            to understanding.
          </h2>
          <p>
            Bring your company knowledge together.
            <br />
            Get grounded answers, with sources you can trust.
          </p>
          <Button onClick={() => (user ? navigate("assistant") : signIn())}>
            Ask Sai Guru
            <ArrowUpRight size={17} />
          </Button>
        </div>
        <div className="knowledge-art" aria-hidden="true">
          <svg viewBox="0 0 460 280">
            <defs>
              <linearGradient id="orb" x1="0" x2="1" y1="0" y2="1">
                <stop stopColor="#d6efab" />
                <stop offset="1" stopColor="#769d62" />
              </linearGradient>
            </defs>
            <ellipse
              cx="240"
              cy="140"
              rx="172"
              ry="74"
              fill="none"
              stroke="#ffffff18"
              transform="rotate(-30 240 140)"
            />
            <ellipse
              cx="240"
              cy="140"
              rx="175"
              ry="95"
              fill="none"
              stroke="#ffffff10"
              transform="rotate(35 240 140)"
            />
            <path
              d="M98 77L239 142L364 58M239 142L362 228M239 142L120 239"
              fill="none"
              stroke="#c4dda766"
              strokeDasharray="4 5"
            />
            <circle cx="239" cy="142" r="58" fill="#b8d29410" />
            <circle cx="239" cy="142" r="43" fill="url(#orb)" />
            <path
              d="M218 145l14 14 29-34M218 130l14 14"
              fill="none"
              stroke="#243d30"
              strokeWidth="3"
              strokeLinecap="round"
            />
            <g fill="#293e3a" stroke="#788a7066">
              <rect
                x="70"
                y="46"
                width="55"
                height="63"
                rx="12"
                transform="rotate(-12 98 77)"
              />
              <rect
                x="337"
                y="31"
                width="55"
                height="58"
                rx="12"
                transform="rotate(12 364 58)"
              />
              <rect
                x="335"
                y="198"
                width="55"
                height="58"
                rx="12"
                transform="rotate(-8 362 228)"
              />
            </g>
            <g stroke="#c6d6b8" fill="none" strokeWidth="2">
              <path d="M87 63h17m-19 9h22m-23 9h20m-19 9h13M353 48h19m-17 9h19m-17 9h10M352 216l-7 9 7 7m17-18l7 9-7 7m-9-16l-3 20" />
            </g>
            <circle cx="120" cy="239" r="7" fill="#c8dba2" />
            <circle cx="300" cy="42" r="3" fill="#c8dba2" />
            <circle cx="150" cy="161" r="3" fill="#c8dba2" />
          </svg>
          <span className="art-caption">
            <Layers3 size={13} /> BUILT ON YOUR SOURCES
          </span>
        </div>
      </section>
      <div className="metrics-grid">
        {stats.map((stat) => (
          <section className="metric-card" key={stat.label}>
            <div className="metric-top">
              <span>{stat.label}</span>
              <stat.icon size={17} />
            </div>
            <strong>{stat.value ?? "—"}</strong>
            <span className="metric-note">{stat.note}</span>
          </section>
        ))}
      </div>
      {loading && <Loading />}
      {!user && (
        <div className="connection-banner">
          <div>
            <BookOpen size={20} />
            <span>
              <strong>Your workspace is ready to connect</strong>
              <small>
                Sign in to see real documents, activity, and metrics.
              </small>
            </span>
          </div>
          <Button variant="secondary" onClick={signIn}>
            Connect workspace
            <ArrowRight size={15} />
          </Button>
        </div>
      )}
      <div className="dashboard-columns">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Recent questions</h2>
              <p>The latest conversations with your knowledge</p>
            </div>
            <CardLink onClick={() => navigate("assistant")}>
              Open assistant
            </CardLink>
          </div>
          {data?.recent_queries.length ? (
            <div className="query-list">
              {data.recent_queries.map((q) => (
                <button
                  key={q.id}
                  className="query-row"
                  onClick={() => inspect(q.id)}
                >
                  <span className="row-icon">
                    <MessageSquare size={17} />
                  </span>
                  <span className="row-main">
                    <strong>{q.question}</strong>
                    <small>
                      {q.route} · {date(q.created_at)} · {latency(q.latency_ms)}
                    </small>
                  </span>
                  <Badge status={q.status}>{q.status.toLowerCase()}</Badge>
                  <ArrowUpRight size={15} />
                </button>
              ))}
            </div>
          ) : (
            <Empty
              title="Your next question starts here"
              description="Ask about a policy, a process, or a product. Your real query activity will appear here."
              action={
                <Button
                  variant="secondary"
                  onClick={() => (user ? navigate("assistant") : signIn())}
                >
                  Start a conversation
                  <ArrowRight size={14} />
                </Button>
              }
            />
          )}
        </section>
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Knowledge library</h2>
              <p>Your recently added sources</p>
            </div>
            <CardLink onClick={() => navigate("documents")}>View all</CardLink>
          </div>
          {data?.recent_documents.length ? (
            data.recent_documents.map((doc) => (
              <div className="document-row" key={doc.id}>
                <span className="file-icon">
                  <FileText size={20} />
                </span>
                <div>
                  <strong>{doc.name}</strong>
                  <small>
                    v{doc.version} · {date(doc.updated_at)}
                  </small>
                </div>
                <Badge status={doc.status}>{doc.status.toLowerCase()}</Badge>
              </div>
            ))
          ) : (
            <Empty
              title="Build your knowledge base"
              description="Upload your first document to turn scattered information into searchable knowledge."
              action={
                <button
                  className="text-link"
                  onClick={() => (user ? navigate("documents") : signIn())}
                >
                  Add your first source
                  <Plus size={14} />
                </button>
              }
            />
          )}
        </section>
      </div>
      <section className="workflow-strip">
        <span className="strip-icon">
          <Sparkles size={20} />
        </span>
        <div>
          <strong>Every answer has a story.</strong>
          <p>
            Follow the evidence from retrieval to the final answer in the
            Retrieval Lab.
          </p>
        </div>
        <Button variant="ghost" onClick={() => navigate("retrieval")}>
          Explore the pipeline
          <ArrowRight size={16} />
        </Button>
      </section>
      <div className="page-footnote">
        {data?.scope ||
          "No demo metrics. Connect your backend to see live workspace data."}
        {data && ` Generation mode: ${data.generation_mode}.`}
      </div>
    </>
  );
}
