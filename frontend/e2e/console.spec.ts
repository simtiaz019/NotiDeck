import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

test("new installation through admin queue cancellation", async ({ page }) => {
  const token = readFileSync(
    process.env.NOTIDECK_E2E_CONFIG + "/bootstrap.token",
    "utf8",
  ).trim();
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Welcome to NotiDeck" }),
  ).toBeVisible();
  await page.getByLabel("Bootstrap token").fill(token);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Test connection" }).click();
  await expect(
    page.getByRole("button", { name: "Connection verified" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Full Name").fill("Test Administrator");
  await page.getByLabel("Username", { exact: true }).fill("admin");
  await page.getByLabel("Email", { exact: true }).fill("admin@example.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill("local-test-pass-123");
  await page.getByLabel("Confirm Password").fill("local-test-pass-123");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("button", { name: "Initialize workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  await page.getByLabel("Username", { exact: true }).fill("admin");
  await page
    .getByLabel("Password", { exact: true })
    .fill("local-test-pass-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Channels", exact: true }).click();
  await page
    .getByRole("button", { name: "Create channel", exact: true })
    .click();
  await page.getByLabel("Name", { exact: true }).fill("Test Webhook");
  await page
    .getByLabel("Url", { exact: true })
    .fill("https://example.com/notifications");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Test Webhook", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Routing rules", exact: true })
    .click();
  await page.getByRole("button", { name: "Create rule", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("Production incidents");
  await expect(
    page
      .getByLabel("Notification template")
      .locator("option", { hasText: "PostgreSQL audit alert" }),
  ).toHaveCount(1);
  await page
    .getByLabel("Notification template")
    .selectOption({ label: "PostgreSQL audit alert" });
  await page.getByRole("checkbox", { name: /Test Webhook/ }).check();
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(
    page.getByText("Production incidents", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sources", exact: true }).click();
  await page
    .getByRole("button", { name: "Create source", exact: true })
    .click();
  await page.getByLabel("Name", { exact: true }).fill("E2E application");
  await page.getByRole("button", { name: "Save changes" }).click();
  await page.getByRole("button", { name: "Keys", exact: true }).click();
  await page
    .getByRole("button", { name: "Create API key", exact: true })
    .click();
  const key = await page.locator(".secret code").textContent();
  const response = await page.request.post("/api/v1/notifications", {
    headers: { Authorization: "Bearer " + key },
    data: {
      title: "E2E notification",
      message: "Persist and route this event",
      severity: "ERROR",
      environment: "production",
      idempotency_key: "e2e-1",
    },
  });
  expect(response.status()).toBe(202);
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page
    .getByRole("button", { name: "Notifications", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "E2E notification", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "E2E notification", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Delivery timeline" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: "Queue", exact: true }).click();
  await page.getByRole("button", { name: "Cancel eligible" }).click();
  await expect(
    page.getByRole("dialog", { name: "Confirm queue operation" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Confirm clear" }).click();
  await expect(page.getByRole("status")).toHaveText("1 deliveries updated.");
  await expect(
    page.getByRole("table").getByText("CANCELLED", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.screenshot({ path: "../docs/console-tested.png", fullPage: true });
  expect(errors).toEqual([]);
});
