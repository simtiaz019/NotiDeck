import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  timeout: 60000,
  use: {
    baseURL: "http://127.0.0.1:8765",
    headless: true,
    channel: process.env.NOTIDECK_BROWSER_CHANNEL || undefined,
    viewport: { width: 1440, height: 1000 },
  },
  reporter: "list",
});
