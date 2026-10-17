import {
  Activity,
  ArrowUpRight,
  BookOpen,
  ChevronDown,
  CircleHelp,
  Command,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  Menu,
  Network,
  Search,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Button, Empty, ErrorNotice, Modal } from "./components/ui";
import { api, hasToken, setToken } from "./lib/api";
import type { User } from "./lib/types";
import { Assistant } from "./pages/Assistant";
import { Dashboard } from "./pages/Dashboard";
import { Documents } from "./pages/Documents";
import { Evaluations } from "./pages/Evaluations";
import { Retrieval } from "./pages/Retrieval";

const navigation = [
  { id: "dashboard", label: "Overview", icon: LayoutDashboard },
  { id: "assistant", label: "Knowledge Assistant", icon: Sparkles },
  { id: "documents", label: "Knowledge Library", icon: BookOpen },
  { id: "retrieval", label: "Retrieval Lab", icon: Network },
  { id: "evaluation", label: "Evaluations", icon: FlaskConical },
];
export default function App() {
  const [page, setPage] = useState("dashboard"),
    [user, setUser] = useState<User | null>(null),
    [loginOpen, setLoginOpen] = useState(false),
    [helpOpen, setHelpOpen] = useState(false),
    [menu, setMenu] = useState(false),
    [health, setHealth] = useState("checking"),
    [queryId, setQueryId] = useState(""),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [loginError, setLoginError] = useState(""),
    [busy, setBusy] = useState(false);
  function navigate(value: string) {
    setPage(value);
    setMenu(false);
  }
  function inspect(id: string) {
    setQueryId(id);
    navigate("retrieval");
  }
  useEffect(() => {
    if (hasToken())
      api<User>("/auth/me")
        .then(setUser)
        .catch(() => setUser(null));
    const check = () =>
      api("/ready", { signal: AbortSignal.timeout(15000) })
        .then(() => setHealth("ready"))
        .catch(() => setHealth("offline"));
    void check();
    const timer = setInterval(() => void check(), 30000);
    const expired = () => {
      setUser(null);
      setLoginError("Your session expired. Sign in again.");
    };
    window.addEventListener("session-expired", expired);
    return () => {
      clearInterval(timer);
      window.removeEventListener("session-expired", expired);
    };
  }, []);
  async function login() {
    setBusy(true);
    setLoginError("");
    try {
      const result = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(result.access_token);
      setUser(await api<User>("/auth/me"));
      setPassword("");
      setLoginOpen(false);
    } catch (e) {
      setLoginError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="app-shell">
      <aside className={`sidebar ${menu ? "mobile-open" : ""}`}>
        <div className="brand">
          <span className="brand-mark">
            <Command size={23} />
          </span>
          <div>
            Sai Guru<span>KNOWLEDGE INTELLIGENCE</span>
          </div>
          <button
            className="mobile-close icon-button"
            aria-label="Close navigation"
            onClick={() => setMenu(false)}
          >
            <X size={19} />
          </button>
        </div>
        <button className="workspace-switch" onClick={() => setHelpOpen(true)}>
          <span className="workspace-avatar">S</span>
          <span>
            <strong>{user?.tenant || "SaiTech workspace"}</strong>
            <small>
              {user ? "Your knowledge workspace" : "Connect to get started"}
            </small>
          </span>
          <ChevronDown size={14} />
        </button>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {navigation.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? "active" : ""}`}
              onClick={() => navigate(item.id)}
            >
              <item.icon size={18} />
              <span>{item.label}</span>
              {item.id === "assistant" && <span className="nav-ai">AI</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="trust-card">
            <span className="trust-icon">
              <ShieldCheck size={20} />
            </span>
            <strong>Grounded in your knowledge.</strong>
            <p>
              Sources you can inspect.
              <br />
              Answers you can understand.
            </p>
            <button onClick={() => setHelpOpen(true)}>
              How Sai Guru works
              <ArrowUpRight size={14} />
            </button>
          </div>
          <button
            className="nav-item help-link"
            onClick={() => setHelpOpen(true)}
          >
            <CircleHelp size={18} />
            Help & getting started
          </button>
          <div className="sidebar-user">
            <span className="user-avatar">
              {user ? user.email[0].toUpperCase() : "S"}
            </span>
            <div>
              <strong>
                {user ? user.email.split("@")[0] : "SaiTech member"}
              </strong>
              <small>{user?.role.toLowerCase() || "Not signed in"}</small>
            </div>
            {user ? (
              <button
                className="icon-button"
                aria-label="Sign out"
                onClick={async () => {
                  try {
                    await api("/auth/logout", { method: "POST" });
                  } catch (error) {
                    setLoginError((error as Error).message);
                    setLoginOpen(true);
                    return;
                  }
                  setToken("");
                  setUser(null);
                  navigate("dashboard");
                }}
              >
                <LogOut size={16} />
              </button>
            ) : (
              <button
                className="icon-button"
                aria-label="Sign in"
                onClick={() => setLoginOpen(true)}
              >
                <ArrowUpRight size={18} />
              </button>
            )}
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="mobile-menu icon-button"
              aria-label="Open navigation"
              onClick={() => setMenu(true)}
            >
              <Menu size={20} />
            </button>
            <span>Workspace</span>
            <span className="breadcrumb-slash">/</span>
            <strong>{navigation.find((n) => n.id === page)?.label}</strong>
          </div>
          <div className="topbar-actions">
            <button
              className="top-search"
              onClick={() => navigate("documents")}
            >
              <Search size={16} />
              <span>Find knowledge</span>
            </button>
            <div className={`system-status ${health}`}>
              <span />
              {health === "ready"
                ? "Database connected"
                : health === "checking"
                  ? "Checking system"
                  : "Backend unavailable"}
            </div>
            {user ? (
              <span className="top-avatar">{user.email[0].toUpperCase()}</span>
            ) : (
              <Button variant="secondary" onClick={() => setLoginOpen(true)}>
                Sign in
              </Button>
            )}
          </div>
        </header>
        <main
          className={
            page === "assistant" && user
              ? "workspace-content assistant-content"
              : "workspace-content"
          }
        >
          {page === "dashboard" ? (
            <Dashboard
              key={user?.id || "signed-out"}
              user={user}
              navigate={navigate}
              signIn={() => setLoginOpen(true)}
              inspect={inspect}
            />
          ) : !user ? (
            <section className="panel">
              <Empty
                title="Connect your knowledge workspace"
                description="Sign in with an account created by your SaiTech administrator to access documents, conversations, and evaluations."
                action={
                  <Button onClick={() => setLoginOpen(true)}>
                    Sign in to Sai Guru
                    <ArrowUpRight size={16} />
                  </Button>
                }
              />
            </section>
          ) : page === "assistant" ? (
            <Assistant inspect={inspect} />
          ) : page === "documents" ? (
            <Documents user={user} />
          ) : page === "retrieval" ? (
            <Retrieval queryId={queryId} />
          ) : user.role === "EMPLOYEE" ? (
            <section className="panel">
              <Empty
                title="Evaluation access is restricted"
                description="Managers and administrators can run and inspect evaluations."
              />
            </section>
          ) : (
            <Evaluations />
          )}
        </main>
        {page !== "assistant" && (
          <footer className="app-footer">
            <span>
              Sai Guru <span className="footer-dot">·</span> AI Knowledge
              Intelligence Platform
            </span>
            <span>
              <Activity size={13} /> Built for clarity
            </span>
          </footer>
        )}
      </div>
      <Modal
        open={loginOpen}
        onClose={() => setLoginOpen(false)}
        title="Welcome to Sai Guru"
        description="Sign in to your team's knowledge workspace."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void login();
          }}
        >
          <ErrorNotice message={loginError} />
          <label className="field">
            Work email
            <input
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@saitech.example"
            />
          </label>
          <label className="field">
            Password
            <input
              type="password"
              required
              autoComplete="current-password"
              maxLength={128}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <Button className="w-full justify-center" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </Button>
          <p className="footnote">
            Accounts are created by your administrator. For local setup, run the
            seed command with your own admin password.
          </p>
        </form>
      </Modal>
      <Modal
        open={helpOpen}
        onClose={() => setHelpOpen(false)}
        title="Your knowledge, with context"
        description="A practical guide to getting started."
      >
        <ol className="help-steps">
          <li>
            <strong>Add your sources</strong>
            <p>
              A manager or admin uploads documents in the Knowledge Library.
            </p>
          </li>
          <li>
            <strong>Process your documents</strong>
            <p>
              Use the Process button or run the ingestion worker to build
              searchable indexes.
            </p>
          </li>
          <li>
            <strong>Ask and inspect</strong>
            <p>
              Ask the Knowledge Assistant. Open a source to inspect its text, or
              use the Retrieval Lab to follow the pipeline.
            </p>
          </li>
          <li>
            <strong>Measure quality</strong>
            <p>
              Seed the fictional SaiTech dataset, then run an evaluation to
              establish a real baseline.
            </p>
          </li>
        </ol>
        <p className="footnote">
          SaiTech is a fictional demo company. Setup and deployment instructions
          are included in the project's docs folder. A model-based grounding
          check can still make mistakes; review evidence for important
          decisions.
        </p>
      </Modal>
    </div>
  );
}
