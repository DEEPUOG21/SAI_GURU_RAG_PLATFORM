import {
  ArrowUp,
  BookOpen,
  Check,
  Copy,
  FileText,
  MessageSquarePlus,
  RotateCcw,
  Search,
  Sparkles,
  Square,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { AnswerMarkdown } from "../components/AnswerMarkdown";
import {
  Badge,
  Button,
  ErrorNotice,
  Modal,
  SourceModal,
} from "../components/ui";
import { api, streamChat } from "../lib/api";
import type { Conversation, Message, Source } from "../lib/types";

export function Assistant({ inspect }: { inspect: (id: string) => void }) {
  const [conversations, setConversations] = useState<Conversation[]>([]),
    [active, setActive] = useState<string>(),
    [messages, setMessages] = useState<Message[]>([]),
    [question, setQuestion] = useState(""),
    [busy, setBusy] = useState(false),
    [stage, setStage] = useState(""),
    [error, setError] = useState(""),
    [confirmDelete, setConfirmDelete] = useState(false),
    [source, setSource] = useState<Source | null>(null),
    [copied, setCopied] = useState(""),
    [feedback, setFeedback] = useState<{ id: string; rating: number } | null>(
      null,
    ),
    [comment, setComment] = useState(""),
    [saved, setSaved] = useState("");
  const abort = useRef<AbortController | null>(null),
    bottom = useRef<HTMLDivElement>(null);
  function refresh() {
    return api<Conversation[]>("/conversations")
      .then(setConversations)
      .catch((e) => setError(e.message));
  }
  useEffect(() => {
    void refresh();
    return () => abort.current?.abort();
  }, []);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, stage]);
  async function select(id: string) {
    if (busy) return;
    setError("");
    try {
      setMessages(await api<Message[]>(`/conversations/${id}/messages`));
      setActive(id);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function send(text = question) {
    if (!text.trim() || busy) return;
    setBusy(true);
    setQuestion("");
    setError("");
    setStage("Starting query");
    setMessages((previous) => [
      ...previous,
      { id: crypto.randomUUID(), role: "user", content: text, citations: [] },
    ]);
    const controller = new AbortController();
    abort.current = controller;
    try {
      await streamChat(
        { question: text, conversation_id: active },
        ({ event, data }) => {
          if (event === "meta") setActive(data.conversation_id as string);
          if (event === "status") setStage(data.stage as string);
          if (event === "reset") setStage("Rechecking the answer");
          if (event === "final") {
            setMessages((previous) => [
              ...previous,
              {
                id: data.message_id as string,
                role: "assistant",
                content: data.answer as string,
                citations: data.citations as Source[],
                query_id: data.query_id as string,
                grounding: data.grounding as string,
                guardrails: data.guardrails as Message["guardrails"],
              },
            ]);
          }
          if (event === "error") {
            setError(`${data.message} Query ID: ${data.query_id}`);
          }
        },
        controller.signal,
      );
      await refresh();
    } catch (e) {
      setError(
        controller.signal.aborted
          ? "Generation stopped before the checks finished."
          : (e as Error).message,
      );
    } finally {
      setBusy(false);
      setStage("");
      abort.current = null;
    }
  }
  async function copy(message: Message) {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(message.id);
      setTimeout(() => setCopied(""), 2000);
    } catch {
      setError("Clipboard access was denied by your browser.");
    }
  }
  async function saveFeedback() {
    if (!feedback) return;
    try {
      await api("/feedback", {
        method: "POST",
        body: JSON.stringify({
          query_id: feedback.id,
          rating: feedback.rating,
          comment,
        }),
      });
      setSaved(feedback.id);
      setFeedback(null);
      setComment("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div className="assistant-layout">
      <aside className="conversation-sidebar">
        <Button
          variant="secondary"
          disabled={busy}
          onClick={() => {
            setActive(undefined);
            setMessages([]);
            setError("");
          }}
        >
          <MessageSquarePlus size={16} />
          New conversation
        </Button>
        <div className="eyebrow mt-7 mb-3">YOUR CONVERSATIONS</div>
        {conversations.length ? (
          conversations.map((c) => (
            <button
              key={c.id}
              disabled={busy}
              className={`conversation-item ${c.id === active ? "selected" : ""}`}
              onClick={() => void select(c.id)}
            >
              <Search size={14} />
              <span>{c.title}</span>
            </button>
          ))
        ) : (
          <p className="muted text-xs leading-6">
            Your conversations will appear here after your first question.
          </p>
        )}
        <div className="conversation-note">
          <BookOpen size={18} />
          <p>Your answers use only the sources your role can access.</p>
        </div>
      </aside>
      <section className="chat-main">
        <div className="chat-header">
          <div>
            <Sparkles size={18} />
            <strong>Knowledge Assistant</strong>
            <Badge>Evidence first</Badge>
          </div>
          {active && (
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => setConfirmDelete(true)}
            >
              Delete conversation
            </Button>
          )}
        </div>
        <div className="chat-messages">
          {!messages.length && (
            <div className="chat-welcome">
              <div className="assistant-orb">
                <Sparkles size={28} />
              </div>
              <div className="eyebrow">MEET YOUR KNOWLEDGE PARTNER</div>
              <h1>
                A better answer starts
                <br />
                with your knowledge.
              </h1>
              <p>
                Ask a question. Follow the sources.
                <br />
                Make your next decision with context.
              </p>
              <div className="suggestion-grid">
                {[
                  "What is our annual leave policy?",
                  "How do I report a security incident?",
                  "What are our remote work guidelines?",
                  "How do I submit an expense claim?",
                ].map((q) => (
                  <button key={q} onClick={() => setQuestion(q)}>
                    <FileText size={16} />
                    <span>{q}</span>
                    <ArrowUp size={13} />
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((message, index) => (
            <article
              className={`message message-${message.role}`}
              key={message.id}
            >
              <div className="message-avatar">
                {message.role === "assistant" ? <Sparkles size={17} /> : "You"}
              </div>
              <div className="message-body">
                <div className="message-label">
                  {message.role === "assistant" ? "Sai Guru" : "You"}
                  {message.grounding && (
                    <Badge status={message.grounding}>
                      {message.grounding === "NOT_APPLICABLE" ||
                      message.grounding === "GENERAL_KNOWLEDGE"
                        ? "General knowledge · not source-verified"
                        : message.grounding.replaceAll("_", " ").toLowerCase()}
                    </Badge>
                  )}
                </div>
                <div className="markdown">
                  <AnswerMarkdown>{message.content}</AnswerMarkdown>
                </div>
                {message.guardrails?.some(
                  (check) => check.action === "REDACT",
                ) && (
                  <p className="muted">
                    Privacy checks removed protected values or unsafe source
                    content. Inspect retrieval for details.
                  </p>
                )}
                {message.citations.length > 0 && (
                  <div className="citations">
                    <span className="eyebrow">SOURCES</span>
                    {message.citations.map((c) => (
                      <button
                        key={c.label}
                        onClick={() => setSource(c)}
                        className="citation"
                      >
                        <FileText size={15} />
                        <span>
                          <strong>
                            {c.label} · {c.document}
                          </strong>
                          <small>
                            {c.page ? `Page ${c.page} · ` : ""}
                            {c.section}
                          </small>
                        </span>
                      </button>
                    ))}
                  </div>
                )}
                {message.role === "assistant" && (
                  <div className="answer-actions">
                    <button
                      className="icon-button"
                      aria-label="Copy answer"
                      title="Copy answer"
                      onClick={() => void copy(message)}
                    >
                      {copied === message.id ? (
                        <Check size={15} />
                      ) : (
                        <Copy size={15} />
                      )}
                    </button>
                    <button
                      className="icon-button"
                      aria-label="Regenerate answer"
                      title="Regenerate answer"
                      disabled={busy}
                      onClick={() =>
                        void send(
                          [...messages.slice(0, index)]
                            .reverse()
                            .find((m) => m.role === "user")?.content || "",
                        )
                      }
                    >
                      <RotateCcw size={15} />
                    </button>
                    {message.query_id && (
                      <>
                        <button
                          className="icon-button"
                          aria-label="Helpful answer"
                          title="Helpful answer"
                          onClick={() =>
                            setFeedback({ id: message.query_id!, rating: 1 })
                          }
                        >
                          <ThumbsUp size={15} />
                        </button>
                        <button
                          className="icon-button"
                          aria-label="Unhelpful answer"
                          title="Unhelpful answer"
                          onClick={() =>
                            setFeedback({ id: message.query_id!, rating: -1 })
                          }
                        >
                          <ThumbsDown size={15} />
                        </button>
                        <button
                          className="text-link"
                          onClick={() => inspect(message.query_id!)}
                        >
                          Inspect retrieval
                        </button>
                        {saved === message.query_id && (
                          <span className="muted text-xs">Feedback saved</span>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            </article>
          ))}
          {busy && (
            <article className="message message-assistant">
              <div className="message-avatar">
                <Sparkles size={17} />
              </div>
              <div className="message-body">
                <div className="message-label">
                  Sai Guru
                  <span className="stream-stage">
                    <span className="pulse-dot" />
                    {stage}
                  </span>
                </div>
              </div>
            </article>
          )}
          <div ref={bottom} />
        </div>
        <div className="composer-wrap">
          <ErrorNotice message={error} />
          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault();
              void send();
            }}
          >
            <textarea
              aria-label="Ask your knowledge base"
              rows={2}
              maxLength={2000}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask anything about your knowledge base…"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
            />
            <div className="composer-bottom">
              <span>
                <BookOpen size={14} />
                Your authorized knowledge base
              </span>
              {busy ? (
                <button
                  type="button"
                  className="send-button"
                  aria-label="Stop generation"
                  onClick={() => abort.current?.abort()}
                >
                  <Square size={15} />
                </button>
              ) : (
                <button
                  className="send-button"
                  aria-label="Send question"
                  disabled={!question.trim()}
                >
                  <ArrowUp size={20} />
                </button>
              )}
            </div>
          </form>
          <p className="composer-note">
            Answers can be imperfect. Review the cited sources. Shift + Enter
            for a new line.
          </p>
        </div>
      </section>
      <SourceModal source={source} onClose={() => setSource(null)} />
      <Modal
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title="Delete this conversation?"
        description="This permanently removes its messages, queries, feedback and retrieval traces."
      >
        <Button
          variant="danger"
          disabled={busy}
          onClick={async () => {
            if (!active) return;
            setBusy(true);
            try {
              await api(`/conversations/${active}`, { method: "DELETE" });
              setActive(undefined);
              setMessages([]);
              setConfirmDelete(false);
              await refresh();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          Delete conversation
        </Button>
      </Modal>
      <Modal
        open={!!feedback}
        onClose={() => setFeedback(null)}
        title="Help improve this answer"
        description="Your feedback is saved against this query."
      >
        <label className="field">
          Additional feedback (optional)
          <textarea
            rows={4}
            maxLength={2000}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="What was useful, or what was missing?"
          />
        </label>
        <Button onClick={() => void saveFeedback()}>Save feedback</Button>
      </Modal>
    </div>
  );
}
