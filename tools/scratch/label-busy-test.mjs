/**
 * Test substrate centre label visibility under high-activity load.
 * Loads the constellation, lets it warm up for 50s so the substrate is
 * actively pulsing with many workflows, then snaps the overview to verify
 * the "the substrate" label is still readable above the bright sphere.
 */
import { chromium } from "playwright";
import { mkdirSync } from "fs";

const URL = "http://localhost:5175/?view=constellation";
const OUT = "/tmp/cstl-shots";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();

page.on("pageerror", (e) => console.log(`PAGE ERROR: ${e.message}`));

await page.goto(URL, { waitUntil: "domcontentloaded" });
await page.waitForSelector("canvas");
console.log("loaded — warming up 35s for high activity...");
await page.waitForTimeout(35_000);

// Snap a big overview frame.
await page.screenshot({ path: `${OUT}/label-busy-overview.png` });
const counts = await page
  .$eval(".constellation__counts", (el) => el.textContent.trim())
  .catch(() => "(none)");
console.log(`counts: ${counts}`);
await browser.close();
console.log("done");
