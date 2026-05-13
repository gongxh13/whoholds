import { expect, test } from "@playwright/test";

/**
 * Smoke / golden-path: each of the five views loads, talks to the backend,
 * and shows the expected empty-state copy when the DB hasn't been bootstrapped.
 * Once a real DB is provisioned, expand these to assert on actual data.
 */
test("landing shows health + nav", async ({ page }) => {
  await page.goto("/#/");
  await expect(page.getByRole("heading", { name: "whoholds" })).toBeVisible();
  await expect(page.getByText("✓ /api/health = ok")).toBeVisible();
  await expect(page.getByRole("link", { name: /#\/discover/ })).toBeVisible();
});

test("discover page renders even on empty DB", async ({ page }) => {
  await page.goto("/#/discover");
  await expect(page.getByRole("heading", { name: "发现" })).toBeVisible();
  await expect(page.getByText("跨持股 个人股东榜")).toBeVisible();
  await expect(page.getByText("协同股东对榜")).toBeVisible();
});

test("network page accepts focus and renders header", async ({ page }) => {
  await page.goto("/#/n/王传福");
  await expect(page.getByRole("heading", { name: /Ego-Network/ })).toBeVisible();
});

test("company 404 surfaces error gracefully", async ({ page }) => {
  await page.goto("/#/c/sh999999");
  // The page shows the 404 message rather than a generic crash.
  await expect(page.getByText(/unknown stock_code/)).toBeVisible({ timeout: 5_000 });
});

test("annotation page can list (empty)", async ({ page }) => {
  await page.goto("/#/annotations");
  await expect(page.getByRole("heading", { name: "用户标注" })).toBeVisible();
});
