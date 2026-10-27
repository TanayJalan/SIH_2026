import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end configuration for the APH demo.
 *
 * The stack (docker compose: postgres, mailpit, backend, frontend) is expected
 * to be running. Override the targets when the demo is served elsewhere, for
 * example on the EC2 host.
 */
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:5173";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
