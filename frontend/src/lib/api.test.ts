import { afterEach, describe, expect, it, vi } from "vitest";
import { SSEParser, streamChat } from "./api";

describe("SSE parser", () => {
  it("handles network fragmentation and keepalive comments", () => {
    const parser = new SSEParser();
    expect(parser.feed(": keepalive\n\nevent: draft\nda")).toEqual([]);
    expect(parser.feed('ta: {"text":"Hello"}\n\n')).toEqual([
      { event: "draft", data: { text: "Hello" } },
    ]);
  });
  it("handles multiple events and CRLF", () => {
    const parser = new SSEParser();
    expect(
      parser
        .feed("event: reset\r\ndata: {}\r\n\r\nevent: done\ndata: {}\n\n")
        .map((e) => e.event),
    ).toEqual(["reset", "done"]);
  });
  it("rejects malformed payloads", () => {
    expect(() => new SSEParser().feed("data: broken\n\n")).toThrow("malformed");
  });
});

describe("chat stream completion", () => {
  afterEach(() => vi.unstubAllGlobals());

  function response(frames: string, close = true) {
    const cancel = vi.fn();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(frames));
        if (close) controller.close();
      },
      cancel,
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body)));
    return cancel;
  }

  it("rejects done without a final answer or explicit error", async () => {
    response(
      'event: draft\ndata: {"text":"provisional"}\n\nevent: done\ndata: {}\n\n',
    );
    await expect(
      streamChat({ question: "q" }, vi.fn(), new AbortController().signal),
    ).rejects.toThrow("without an answer");
  });

  it("rejects truncated transport even after a provisional draft", async () => {
    response('event: draft\ndata: {"text":"provisional"}\n\n');
    await expect(
      streamChat({ question: "q" }, vi.fn(), new AbortController().signal),
    ).rejects.toThrow("before the answer was completed");
  });

  it.each(["final", "error"])(
    "finishes after %s and done without waiting for socket closure",
    async (event) => {
      const cancel = response(
        `event: ${event}\ndata: {}\n\nevent: done\ndata: {}\n\n`,
        false,
      );
      const received: string[] = [];
      await streamChat(
        { question: "q" },
        (frame) => received.push(frame.event),
        new AbortController().signal,
      );
      expect(received).toEqual([event, "done"]);
      expect(cancel).toHaveBeenCalledOnce();
    },
  );
});
