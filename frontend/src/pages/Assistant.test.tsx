import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { StreamEvent } from "../lib/api";
import { Assistant } from "./Assistant";

const state = vi.hoisted(() => ({ release: () => {} }));
vi.mock("../lib/api", () => ({
  api: vi.fn(async () => []),
  streamChat: vi.fn(
    async (_body: unknown, onEvent: (event: StreamEvent) => void) => {
      onEvent({
        event: "draft",
        data: { text: "UNSAFE_DRAFT_MUST_NEVER_APPEAR" },
      });
      await new Promise<void>((resolve) => {
        state.release = resolve;
      });
      onEvent({
        event: "final",
        data: {
          answer: "Safe checked answer.",
          message_id: "m",
          citations: [],
          grounding: "NOT_APPLICABLE",
          guardrails: [],
        },
      });
      onEvent({ event: "done", data: {} });
    },
  ),
}));

it("never displays legacy draft events while waiting for the checked final answer", async () => {
  HTMLElement.prototype.scrollIntoView = vi.fn();
  const { streamChat } = await import("../lib/api");
  render(<Assistant inspect={vi.fn()} />);
  fireEvent.change(
    screen.getByRole("textbox", { name: "Ask your knowledge base" }),
    { target: { value: "Hello" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Send question" }));
  await waitFor(() => expect(streamChat).toHaveBeenCalledOnce());
  expect(screen.queryByText("UNSAFE_DRAFT_MUST_NEVER_APPEAR")).toBeNull();
  await act(async () => {
    state.release();
  });
  expect(await screen.findByText("Safe checked answer.")).toBeTruthy();
});
