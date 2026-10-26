const base = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(
  /\/$/,
  "",
);
let token = sessionStorage.getItem("sai-token") || "";
export function setToken(value: string) {
  token = value;
  if (value) sessionStorage.setItem("sai-token", value);
  else sessionStorage.removeItem("sai-token");
}
export function hasToken() {
  return Boolean(token);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(`${base}/api/v1${path}`, {
      ...init,
      headers,
      signal:
        init.signal ||
        AbortSignal.timeout(
          path.endsWith("/process") || path === "/evaluation/run"
            ? 650000
            : 20000,
        ),
    });
  } catch (error) {
    throw new Error(
      error instanceof DOMException && error.name === "TimeoutError"
        ? "The request timed out. Check the backend and retry."
        : "Cannot reach the API. Check the backend URL and connection.",
    );
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    if (response.status === 401) {
      setToken("");
      window.dispatchEvent(new Event("session-expired"));
    }
    throw new Error(
      data?.error?.message || `Request failed (${response.status})`,
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export type StreamEvent = { event: string; data: Record<string, unknown> };
export class SSEParser {
  private buffer = "";
  feed(chunk: string): StreamEvent[] {
    this.buffer += chunk;
    this.buffer = this.buffer.replace(/\r\n/g, "\n");
    const frames = this.buffer.split("\n\n");
    this.buffer = frames.pop() || "";
    return frames.flatMap((frame) => {
      const lines = frame.split("\n");
      const event =
        lines
          .find((line) => line.startsWith("event:"))
          ?.slice(6)
          .trim() || "message";
      const data = lines
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (!data) return [];
      try {
        return [{ event, data: JSON.parse(data) }];
      } catch {
        throw new Error("The server sent a malformed stream.");
      }
    });
  }
}

export async function streamChat(
  body: { question: string; conversation_id?: string },
  onEvent: (event: StreamEvent) => void,
  signal: AbortSignal,
) {
  const response = await fetch(`${base}/api/v1/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    if (response.status === 401) {
      setToken("");
      window.dispatchEvent(new Event("session-expired"));
    }
    throw new Error(
      error?.error?.message || `Chat failed (${response.status})`,
    );
  }
  const reader = response.body?.getReader();
  if (!reader) throw new Error("Streaming is not supported by this browser.");
  const parser = new SSEParser(),
    decoder = new TextDecoder();
  let doneEvent = false;
  let terminalEvent = false;
  try {
    while (true) {
      const { done, value } = await reader.read();
      const events = parser.feed(
        done ? decoder.decode() : decoder.decode(value, { stream: true }),
      );
      for (const event of events) {
        if (event.event === "final" || event.event === "error")
          terminalEvent = true;
        if (event.event === "done") {
          doneEvent = true;
          if (!terminalEvent)
            throw new Error(
              "The stream ended without an answer. Please retry.",
            );
        }
        onEvent(event);
        if (doneEvent) break;
      }
      if (done || doneEvent) break;
    }
    if (!doneEvent)
      throw new Error(
        "Connection ended before the answer was completed. Please retry.",
      );
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
