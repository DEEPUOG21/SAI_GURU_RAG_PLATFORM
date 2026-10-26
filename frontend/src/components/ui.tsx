import * as Dialog from "@radix-ui/react-dialog";
import {
  AlertCircle,
  ArrowUpRight,
  FileSearch,
  LoaderCircle,
  X,
} from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { Source } from "../lib/types";

export function Button({
  children,
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  return (
    <button className={`btn btn-${variant} ${className}`} {...props}>
      {children}
    </button>
  );
}
export function Badge({
  children,
  status = "",
}: {
  children: ReactNode;
  status?: string;
}) {
  return (
    <span
      className={`badge ${["COMPLETED", "SUPPORTED", "ready"].includes(status) ? "badge-green" : ["FAILED", "UNSUPPORTED", "REFUSED"].includes(status) ? "badge-red" : ""}`}
    >
      {children}
    </span>
  );
}
export function ErrorNotice({ message }: { message: string }) {
  return message ? (
    <div className="error-notice" role="alert">
      <AlertCircle size={17} />
      <span>{message}</span>
    </div>
  ) : null;
}
export function Loading({ label = "Loading workspace…" }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={20} />
      {label}
    </div>
  );
}
export function Empty({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <FileSearch size={25} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(value) => {
        if (!value) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content className="modal-content">
          <div className="modal-head">
            <div>
              <Dialog.Title>{title}</Dialog.Title>
              <Dialog.Description>
                {description || "Workspace details"}
              </Dialog.Description>
            </div>
            <Dialog.Close className="icon-button" aria-label="Close dialog">
              <X size={20} />
            </Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function SourceModal({
  source,
  onClose,
}: {
  source: Source | null;
  onClose: () => void;
}) {
  return (
    <Modal
      open={!!source}
      onClose={onClose}
      title={source?.document || "Source"}
      description="Original evidence supplied to the answer generator."
    >
      {source && (
        <>
          <div className="source-meta">
            <Badge>{source.label}</Badge>
            <span>
              {source.page ? `Page ${source.page}` : "No page metadata"}
            </span>
            <span>{source.section}</span>
            {source.version && <span>Version {source.version}</span>}
          </div>
          <pre className="source-text">{source.text}</pre>
          <div className="muted text-xs">
            Chunk ID: {source.chunk_id || "SQL result; no document chunk"}
          </div>
        </>
      )}
    </Modal>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function CardLink({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button className="text-link" onClick={onClick}>
      {children}
      <ArrowUpRight size={15} />
    </button>
  );
}
export const date = (value: string) =>
  new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
export const latency = (value: number | null | undefined) =>
  value == null ? "—" : `${(value / 1000).toFixed(2)}s`;
