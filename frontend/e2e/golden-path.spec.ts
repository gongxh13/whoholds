import { expect, test } from "@playwright/test";

/**
 * Smoke / golden-path: each of the five views loads, talks to the backend,
 * and shows the expected empty-state copy when the DB hasn't been bootstrapped.
 * Once a real DB is provisioned, expand these to assert on actual data.
 */
test("landing is Discover (跨持股 + 协同对榜)", async ({ page }) => {
  await page.goto("/#/");
  await expect(page.getByRole("heading", { name: /发现/ })).toBeVisible();
  await expect(page.getByText("跨持股个人股东榜")).toBeVisible();
  await expect(page.getByText("协同股东对榜")).toBeVisible();
});

test("/#/discover renders the same Discover page", async ({ page }) => {
  await page.goto("/#/discover");
  await expect(page.getByText("跨持股个人股东榜")).toBeVisible();
});

test("status page surfaces 5 DB pills", async ({ page }) => {
  await page.goto("/#/health");
  await expect(page.getByText("/api/health = ok")).toBeVisible();
  for (const db of ["holdings.db", "prices.db", "entities.db", "wd_cache.db", "meta.db"]) {
    await expect(page.getByText(db)).toBeVisible();
  }
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
