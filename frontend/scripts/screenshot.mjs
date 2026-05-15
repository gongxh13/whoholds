// Visual loop helper — take screenshots of every page in both themes
// and write to /tmp/whoholds-shots/ so the agent can Read them.
import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";

const OUT = process.env.SHOTS_DIR ?? "/tmp/whoholds-shots";
const BASE = "http://localhost:5174";

const PAGES = [
  { name: "01-discover", path: "/" },
  { name: "02-company", path: "/c/sz000333" },
  { name: "03-person-hub", path: `/p/${encodeURIComponent("吕强")}` },
  { name: "04-person-entity", path: `/p/${encodeURIComponent("王传福")}` },
  { name: "05-network", path: `/n/${encodeURIComponent("王传福")}` },
  { name: "06-annotations", path: "/annotations" },
  { name: "07-health", path: "/health" },
];

const THEMES = ["light", "dark"];

async function shoot() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch();

  for (const theme of THEMES) {
    // Fresh context per theme so init script + colorScheme apply cleanly.
    const ctx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      deviceScaleFactor: 1.5,
      colorScheme: theme === "dark" ? "dark" : "light",
    });
    // Inject localStorage BEFORE any page script runs, so React's useState
    // initializer reads the correct theme on first render.
    await ctx.addInitScript((t) => {
      try {
        localStorage.setItem("whoholds.theme", t);
      } catch {}
    }, theme);
    const page = await ctx.newPage();

    for (const p of PAGES) {
      const url = `${BASE}/#${p.path}`;
      await page.goto(url, { waitUntil: "domcontentloaded" });
      await page.waitForSelector("header a[href='#/']", { timeout: 5000 }).catch(() => null);
      await page.waitForTimeout(2500);
      const file = `${OUT}/${p.name}-${theme}.png`;
      await page.screenshot({ path: file, fullPage: true });
      console.log(`✓ ${file}`);
    }
    await ctx.close();
  }
  await browser.close();
}

shoot().catch((e) => {
  console.error(e);
  process.exit(1);
});
