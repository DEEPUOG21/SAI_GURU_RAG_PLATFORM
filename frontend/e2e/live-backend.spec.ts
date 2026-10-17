import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

test("real backend: sign in, upload, index, preview, delete and ask with citations", async ({
  page,
}) => {
  test.skip(
    process.env.SAI_E2E_LIVE !== "1",
    "Requires seeded local API, database and inference service.",
  );
  test.setTimeout(240000);
  const env = Object.fromEntries(
    readFileSync("../.env", "utf8")
      .split(/\r?\n/)
      .filter((line) => line && !line.startsWith("#"))
      .map((line) => {
        const position = line.indexOf("=");
        return [line.slice(0, position), line.slice(position + 1)];
      }),
  );
  await page.goto("/");
  await page
    .getByRole("button", { name: "Sign in", exact: true })
    .last()
    .click();
  await page.getByLabel("Work email").fill(env.SEED_ADMIN_EMAIL);
  await page
    .getByLabel("Password", { exact: true })
    .fill(env.SEED_ADMIN_PASSWORD);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Sign in", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page
    .getByRole("button", { name: "Knowledge Library", exact: true })
    .click();
  const filename = `Browser-check-${Date.now()}.md`;
  await page.locator("input[type=file]").setInputFiles({
    name: filename,
    mimeType: "text/markdown",
    buffer: Buffer.from(
      "# Browser verification\n\nThis is a temporary synthetic document used to verify upload and indexing.",
    ),
  });
  await expect(
    page.getByRole("button", { name: filename }).first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: `Process ${filename}`, exact: true })
    .click();
  const row = page.locator("tr").filter({
    has: page.getByRole("button", { name: filename, exact: false }),
  });
  await expect(row).toContainText("COMPLETED", { timeout: 90000 });
  await page.getByRole("button", { name: filename }).first().click();
  await expect(page.getByRole("dialog")).toContainText(
    "temporary synthetic document",
  );
  await page.getByLabel("Close dialog").click();
  await page
    .getByRole("button", { name: `Delete ${filename}`, exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Delete document", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page
    .getByRole("button", { name: "Knowledge Assistant", exact: false })
    .first()
    .click();
  await page
    .getByLabel("Ask your knowledge base")
    .fill(
      "How many paid annual leave days do full-time SaiTech employees receive?",
    );
  await page.getByLabel("Send question").click();
  await expect(
    page.getByText("Provisional draft · not yet verified"),
  ).toBeVisible({ timeout: 90000 });
  await expect(
    page.getByRole("button", { name: /Source 1.*Leave-Policy/ }),
  ).toBeVisible({ timeout: 120000 });
  await page.screenshot({
    path: "test-results/assistant-live.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: /Source 1.*Leave-Policy/ }).click();
  await expect(page.getByRole("dialog")).toContainText("24 working days");
  await page.getByLabel("Close dialog").click();
  await page.getByLabel("Ask your knowledge base").fill("How does it accrue?");
  await page.getByLabel("Send question").click();
  await expect(
    page.getByRole("button", { name: /Source 1.*Leave-Policy/ }),
  ).toHaveCount(2, { timeout: 150000 });
  await expect(page.locator(".message-body").last()).toContainText(
    /two days|2 days/i,
  );
  await page
    .getByRole("button", { name: "Inspect retrieval", exact: true })
    .last()
    .click();
  await expect(
    page.getByRole("heading", { name: "Retrieved evidence", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/retrieval-live.png",
    fullPage: true,
  });
});
