import { defineConfig, devices } from "@playwright/test";

/**
 * Golden-path e2e for the four-view UI per design.md.
 *
 * Boots the FastAPI backend (no scheduler, isolated tmp DB) + vite dev server
 * via webServer, then drives the browser at http://localhost:5174.
 *
 * Run locally:  pnpm exec playwright install chromium && pnpm e2e
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5174",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command:
        "cd ../backend && WHOHOLDS_DISABLE_SCHEDULER=1 WHOHOLDS_DATA_DIR=$(mktemp -d) uv run python -c 'from app.db.migrations import migrate_all; migrate_all()' && WHOHOLDS_DISABLE_SCHEDULER=1 uv run uvicorn app.main:app --port 8000",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "pnpm dev",
      url: "http://localhost:5174",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
