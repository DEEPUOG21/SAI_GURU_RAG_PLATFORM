import { describe, expect, it } from "vitest";
import { SSEParser } from "./api";

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
