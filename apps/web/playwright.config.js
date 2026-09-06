// Riff web E2E: the real Next app against a fake-provider API (no Claude, no engine). `pnpm test:e2e`.
const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 1,
  workers: 1,
  use: { baseURL: "http://localhost:3100", trace: "retain-on-failure" },
  webServer: [
    { command: "./e2e/run-api.sh", url: "http://127.0.0.1:8011/health", reuseExistingServer: false, timeout: 120_000 },
    { command: "NEXT_DIST_DIR=.next-e2e NEXT_PUBLIC_API_URL=http://127.0.0.1:8011 pnpm exec next dev --port 3100", url: "http://localhost:3100", reuseExistingServer: false, timeout: 120_000 },
  ],
});
