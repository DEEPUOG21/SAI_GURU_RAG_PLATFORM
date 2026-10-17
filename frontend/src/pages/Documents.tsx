import {
  FileText,
  Filter,
  LoaderCircle,
  Play,
  Search,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Badge,
  Button,
  date,
  Empty,
  ErrorNotice,
  Modal,
  PageHeading,
} from "../components/ui";
import { api } from "../lib/api";
import type { Document, User } from "../lib/types";

type Detail = Document & {
  chunk_count: number;
  chunks: { id: string; text: string; page: number | null; section: string }[];
};
export function Documents({ user }: { user: User }) {
  const [docs, setDocs] = useState<Document[]>([]),
    [search, setSearch] = useState(""),
    [status, setStatus] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(""),
    [detail, setDetail] = useState<Detail | null>(null),
    [deleting, setDeleting] = useState<Document | null>(null),
    [role, setRole] = useState(0);
  const [uploadLimit, setUploadLimit] = useState(10);
  const input = useRef<HTMLInputElement>(null),
    canEdit = user.role !== "EMPLOYEE";
  const refresh = useCallback(
    () =>
      api<Document[]>(
        `/documents?search=${encodeURIComponent(search)}&status=${status}`,
      )
        .then(setDocs)
        .catch((e) => setError(e.message)),
    [search, status],
  );
  useEffect(() => {
    void api<{ max_upload_mb?: number }>("/health")
      .then((config) => {
        if (config.max_upload_mb) setUploadLimit(config.max_upload_mb);
      })
      .catch(() => {});
  }, []);
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 5000);
    return () => clearInterval(timer);
  }, [refresh]);
  async function upload(files: FileList | null) {
    if (!files || !canEdit) return;
    setError("");
    setBusy("upload");
    try {
      for (const file of Array.from(files)) {
        if (file.size > uploadLimit * 1024 * 1024)
          throw new Error(`${file.name} exceeds ${uploadLimit} MB.`);
        const form = new FormData();
        form.append("file", file);
        form.append("min_role", String(role));
        await api("/documents", { method: "POST", body: form });
      }
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
      if (input.current) input.current.value = "";
    }
  }
  async function process(id: string) {
    setBusy(id);
    setError("");
    try {
      await api(`/documents/${id}/process`, { method: "POST" });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function remove() {
    if (!deleting) return;
    setBusy(deleting.id);
    try {
      await api(`/documents/${deleting.id}`, { method: "DELETE" });
      setDeleting(null);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function preview(id: string) {
    try {
      setDetail(await api<Detail>(`/documents/${id}`));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="KNOWLEDGE LIBRARY"
        title="A source for every answer."
        description="Manage, index, and inspect your team's shared knowledge."
        action={
          canEdit && (
            <Button disabled={!!busy} onClick={() => input.current?.click()}>
              <UploadCloud size={17} />
              Upload documents
            </Button>
          )
        }
      />
      <ErrorNotice message={error} />
      <input
        ref={input}
        type="file"
        className="sr-only"
        accept=".pdf,.docx,.txt,.md,.html,.csv,.json"
        multiple
        onChange={(e) => void upload(e.target.files)}
        aria-label="Upload documents"
      />
      {canEdit && (
        <div
          className="upload-zone"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (!busy) void upload(e.dataTransfer.files);
          }}
        >
          <div className="upload-circle">
            <UploadCloud size={26} />
          </div>
          <h3>Give your knowledge a home</h3>
          <p>
            Drop documents here or{" "}
            <button
              className="inline-link"
              disabled={!!busy}
              onClick={() => input.current?.click()}
            >
              browse files
            </button>
          </p>
          <small>
            PDF, DOCX, TXT, Markdown, HTML, CSV, JSON · Up to {uploadLimit} MB
            per file
          </small>
          <label className="access-select">
            Who can access these documents?
            <select
              value={role}
              onChange={(e) => setRole(Number(e.target.value))}
            >
              <option value={0}>Everyone in your tenant</option>
              <option value={1}>Managers and admins</option>
              {user.role === "ADMIN" && <option value={2}>Admins only</option>}
            </select>
          </label>
          {busy === "upload" && <span className="muted">Uploading…</span>}
        </div>
      )}
      <section className="panel">
        <div className="table-toolbar">
          <div className="search-field">
            <Search size={17} />
            <input
              aria-label="Search documents"
              placeholder="Search your documents…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="filter-field">
            <Filter size={15} />
            <select
              aria-label="Filter processing status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">All statuses</option>
              {[
                "UPLOADED",
                "PARSING",
                "CHUNKING",
                "EMBEDDING",
                "INDEXING",
                "COMPLETED",
                "FAILED",
              ].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </div>
          <span className="muted text-xs">{docs.length} documents shown</span>
        </div>
        {docs.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Document name</th>
                  <th>Status</th>
                  <th>Access</th>
                  <th>Version</th>
                  <th>Updated</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((doc) => (
                  <tr key={doc.id}>
                    <td>
                      <button
                        className="document-name"
                        onClick={() => void preview(doc.id)}
                      >
                        <span className="file-icon">
                          <FileText size={20} />
                        </span>
                        <span>
                          {doc.name}
                          <small>{(doc.size / 1024).toFixed(1)} KB</small>
                        </span>
                      </button>
                    </td>
                    <td>
                      <Badge status={doc.status}>{doc.status}</Badge>
                      {doc.error && (
                        <small className="error-text">{doc.error}</small>
                      )}
                    </td>
                    <td>{["Everyone", "Managers+", "Admins"][doc.min_role]}</td>
                    <td>v{doc.version}</td>
                    <td>{date(doc.updated_at)}</td>
                    <td>
                      <div className="row-actions">
                        {canEdit && (
                          <>
                            <button
                              className="icon-button"
                              title="Process or retry document"
                              aria-label={`Process ${doc.name}`}
                              disabled={!!busy || doc.status === "COMPLETED"}
                              onClick={() => void process(doc.id)}
                            >
                              {busy === doc.id ? (
                                <LoaderCircle className="spin" size={16} />
                              ) : (
                                <Play size={16} />
                              )}
                            </button>
                            <button
                              className="icon-button danger"
                              title="Delete document"
                              aria-label={`Delete ${doc.name}`}
                              disabled={!!busy}
                              onClick={() => setDeleting(doc)}
                            >
                              <Trash2 size={16} />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="No documents found"
            description={
              search || status
                ? "Try a different search or processing status."
                : "Upload a source, then select Process to build its vector and full-text indexes."
            }
          />
        )}
      </section>
      <p className="page-footnote">
        Uploading the same filename creates a new version only when its content
        or access changes. Indexing runs through the worker or the Process
        button.
      </p>
      <Modal
        open={!!detail}
        onClose={() => setDetail(null)}
        title={detail?.name || "Document"}
        description={`${detail?.chunk_count || 0} indexed chunks · Showing up to 50`}
      >
        {detail?.chunks.length ? (
          detail.chunks.map((chunk) => (
            <div className="chunk-preview" key={chunk.id}>
              <div className="source-meta">
                <Badge>{chunk.section}</Badge>
                <span>
                  {chunk.page ? `Page ${chunk.page}` : "No page metadata"}
                </span>
              </div>
              <p>{chunk.text}</p>
              <small className="muted">{chunk.id}</small>
            </div>
          ))
        ) : (
          <Empty
            title="No indexed text yet"
            description="Process this document to inspect extracted chunks. Check the status for parsing or provider errors."
          />
        )}
      </Modal>
      <Modal
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Delete this document?"
        description="This removes the original file, all versions, and searchable chunks."
      >
        <p className="mb-5">{deleting?.name}</p>
        <div className="row-actions">
          <Button variant="secondary" onClick={() => setDeleting(null)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            disabled={!!busy}
            onClick={() => void remove()}
          >
            Delete document
          </Button>
        </div>
      </Modal>
    </>
  );
}
