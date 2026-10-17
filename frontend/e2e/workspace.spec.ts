import { expect, test } from "@playwright/test";

test("dashboard has honest empty states and usable navigation", async ({
  page,
}) => {
  await page.route("**/api/v1/ready", (route) =>
    route.fulfill({
      status: 503,
      json: { error: { message: "Unavailable in this UI test" } },
    }),
  );
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Knowledge, connected." }),
  ).toBeVisible();
  await expect(page.getByText("Backend unavailable")).toBeVisible();
  await expect(page.getByText("Your next question starts here")).toBeVisible();
  await page
    .getByRole("button", { name: "Connect workspace", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByLabel("Work email").fill("test@saitech.example");
  await page.getByLabel("Password", { exact: true }).fill("test-only-password");
  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({
      status: 401,
      json: { error: { message: "Incorrect email or password." } },
    }),
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Sign in", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Incorrect email or password.",
  );
  await page.screenshot({
    path: "test-results/login-desktop.png",
    fullPage: true,
  });
  await page.getByLabel("Close dialog").click();
  await page.screenshot({
    path: "test-results/dashboard-desktop.png",
    fullPage: true,
  });
});

test("mobile navigation fits the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/v1/ready", (route) =>
    route.fulfill({
      status: 503,
      json: { error: { message: "Unavailable in this UI test" } },
    }),
  );
  await page.goto("/");
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.getByLabel("Open navigation").click();
  await page
    .getByRole("button", { name: "Knowledge Library", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Connect your knowledge workspace" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/mobile.png",
    fullPage: true,
    animations: "disabled",
  });
});
