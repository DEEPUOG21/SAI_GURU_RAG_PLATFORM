import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import App from "./App";
import { api, setToken } from "./lib/api";

vi.mock("./lib/api", () => ({
  api: vi.fn(),
  hasToken: () => false,
  setToken: vi.fn(),
}));
vi.mock("./pages/Dashboard", () => ({
  Dashboard: () => <div>Workspace overview</div>,
}));

beforeEach(() => {
  vi.mocked(api).mockImplementation(async (path) => {
    if (path === "/auth/signup") return { access_token: "signup-token" };
    if (path === "/auth/me")
      return {
        id: "new-user",
        email: "new@user.test",
        role: "ADMIN",
        tenant: "New team",
      };
    return {};
  });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function signupForm(confirm = "a-long-signup-password") {
  fireEvent.click(screen.getByRole("button", { name: "Sign up" }));
  const dialog = within(screen.getByRole("dialog"));
  for (const [name, value] of [
    ["Workspace name", "New team"],
    ["Work email", "new@user.test"],
    ["Password", "a-long-signup-password"],
    ["Confirm password", confirm],
  ])
    fireEvent.change(dialog.getByLabelText(name, { exact: true }), {
      target: { value },
    });
  return dialog;
}

test("new users can create a private workspace and enter their session", async () => {
  render(<App />);
  const dialog = signupForm();
  fireEvent.click(
    dialog.getByRole("button", { name: "Create account" }),
  );
  await waitFor(() => expect(setToken).toHaveBeenCalledWith("signup-token"));
  expect(api).toHaveBeenCalledWith("/auth/signup", {
    method: "POST",
    body: JSON.stringify({
      email: "new@user.test",
      password: "a-long-signup-password",
      workspace_name: "New team",
    }),
  });
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(screen.getByText("New team")).toBeTruthy();
});

test("password mismatch stays on the form without sending registration", () => {
  render(<App />);
  const dialog = signupForm("different-password");
  fireEvent.click(
    dialog.getByRole("button", { name: "Create account" }),
  );
  expect(dialog.getByText("Passwords do not match.")).toBeTruthy();
  expect(
    vi.mocked(api).mock.calls.some(([path]) => path === "/auth/signup"),
  ).toBe(false);
});

test("users can return from registration to the existing sign-in form", () => {
  render(<App />);
  const dialog = signupForm();
  fireEvent.click(
    dialog.getByRole("button", { name: "Already have an account? Sign in" }),
  );
  expect(dialog.queryByLabelText("Workspace name")).toBeNull();
  expect(
    dialog.getByRole("button", { name: "Sign in" }),
  ).toBeTruthy();
});
