import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { Dashboard } from "./Dashboard";

afterEach(cleanup);
test("signed-out dashboard does not fabricate activity or metrics", () => {
  render(
    <Dashboard
      user={null}
      navigate={vi.fn()}
      signIn={vi.fn()}
      inspect={vi.fn()}
    />,
  );
  expect(screen.getAllByText("—")).toHaveLength(4);
  expect(screen.getByText("Your next question starts here")).toBeTruthy();
  expect(screen.getByText("Build your knowledge base")).toBeTruthy();
});
