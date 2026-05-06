/**
 * Headless visual sanity check for the Constellation.
 *
 * Loads the standalone constellation page, listens for console errors,
 * waits for the live SSE stream to start delivering events, then takes
 * a series of timestamped screenshots so we can eyeball that:
 *   - the canvas renders at all (no blank page)
 *   - substrate dots are visible (centre sphere is bright)
 *   - photon arcs appear when events fire
 *   - counts ribbon updates over time
 *
 * Output: PNGs in /tmp/cstl-shots/<label>-<n>.png
 *
 * Usage: node tools/scratch/constellation-visual-check.mjs <label>
 */

import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "fs";

const LABEL = process.argv[2] || "run";
const URL = process.env.URL || "http://localhost:5175/?view=constellation";
const OUT = "/tmp/cstl-shots";
mkdirSync(OUT, { recursive: true });

function ts() {
  const d = new Date();
  return d.toTimeString().slice(0, 8);
}

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  viewport: { width: 1600, height: 1000 },
  deviceScaleFactor: 1,
});
const page = await ctx.newPage();

const consoleErrors = [];
const pageErrors = [];

page.on("console", (msg) => {
  const t = msg.type();
  if (t === "error" || t === "warning") {
    consoleErrors.push(`[${t}] ${msg.text()}`);
  }
});
page.on("pageerror", (err) => {
  pageErrors.push(`${err.name}: ${err.message}`);
});

console.log(`[${ts()}] navigating to ${URL}`);
await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 30_000 });

// Wait for the canvas to mount.
await page
  .waitForSelector("canvas", { timeout: 15_000 })
  .catch(() => console.log(`[${ts()}] WARN: no canvas selector after 15s`));

// Snap immediately after mount.
await page.screenshot({ path: `${OUT}/${LABEL}-01-mount.png`, fullPage: false });
console.log(`[${ts()}] snap 01 mount`);

// Sample observatory state by reading from the SSE endpoint directly so
// we can attest activity rather than just trusting "looks alive".
const stream = await fetch(URL.replace(/\?.*$/, "").replace(/:\d+$/, ":3001") + "/api/blueprint/stream", {
  // Tiny timeout via AbortController.
}).catch((e) => ({ ok: false, err: String(e) }));
console.log(`[${ts()}] SSE probe: status=${stream.status ?? stream.err}`);

// Wait 6s for activity, snap.
await page.waitForTimeout(6_000);
await page.screenshot({ path: `${OUT}/${LABEL}-02-after6s.png` });
console.log(`[${ts()}] snap 02 after 6s`);

// Wait a chunkier slice — give SSE replay time to start hitting HITL gates.
await page.waitForTimeout(15_000);
await page.screenshot({ path: `${OUT}/${LABEL}-03-after21s.png` });
console.log(`[${ts()}] snap 03 after 21s`);

// Click into a domain by pressing the first nav-panel domain entry, snap MID lod.
const flew = await page
  .evaluate(() => {
    const btns = Array.from(
      document.querySelectorAll(".constellation__nav-item"),
    ).filter((b) => !b.classList.contains("constellation__nav-item--reset"));
    if (btns.length === 0) return null;
    btns[0].click();
    const label = btns[0].querySelector(".constellation__nav-label");
    return label ? label.textContent : "(unknown)";
  })
  .catch(() => null);
console.log(`[${ts()}] flew to ${flew}`);
await page.waitForTimeout(4_000);
await page.screenshot({ path: `${OUT}/${LABEL}-04-zoomed.png` });
console.log(`[${ts()}] snap 04 zoomed`);

// Keyboard: 0 returns to overview.
await page.keyboard.press("0");
await page.waitForTimeout(2_500);
await page.screenshot({ path: `${OUT}/${LABEL}-05-keyboard-0.png` });
console.log(`[${ts()}] snap 05 after key 0 (overview)`);

// Keyboard: 3 jumps to the third nav-panel cluster.
await page.keyboard.press("3");
await page.waitForTimeout(3_500);
await page.screenshot({ path: `${OUT}/${LABEL}-06-keyboard-3.png` });
console.log(`[${ts()}] snap 06 after key 3`);

// Keyboard: P toggles projector mode on.
await page.keyboard.press("0");
await page.waitForTimeout(1_500);
await page.keyboard.press("p");
await page.waitForTimeout(1_000);
await page.screenshot({ path: `${OUT}/${LABEL}-07-projector-on.png` });
const projectorState = await page
  .$eval(".constellation__projector", (el) => el.textContent)
  .catch(() => "(no toggle)");
console.log(`[${ts()}] snap 07 projector toggle text: "${projectorState}"`);

// Wait long enough (15s) for the projector tick (9s) to fire and move the camera.
await page.waitForTimeout(15_000);
await page.screenshot({ path: `${OUT}/${LABEL}-08-projector-after15s.png` });
console.log(`[${ts()}] snap 08 projector after 15s`);

// Read the live counts from the DOM so we can attest activity numerically.
const counts = await page
  .$eval(".constellation__counts", (el) => el.textContent.trim())
  .catch(() => "(no counts ribbon)");
console.log(`[${ts()}] counts: ${counts}`);

// Read the live legend so we can attest the new two-row form is rendering.
const legend = await page
  .$eval(".constellation__hud-legend", (el) =>
    el.textContent.trim().replace(/\s+/g, " "),
  )
  .catch(() => "(no legend)");
console.log(`[${ts()}] legend: ${legend}`);

await browser.close();

const summary = {
  label: LABEL,
  url: URL,
  pageErrors,
  consoleErrors,
  counts,
  legend,
  flew,
  projectorState,
  shots: 8,
};
writeFileSync(`${OUT}/${LABEL}.json`, JSON.stringify(summary, null, 2));

console.log("---");
console.log(`pageErrors: ${pageErrors.length}`);
pageErrors.forEach((e) => console.log("  " + e));
console.log(`consoleErrors: ${consoleErrors.length}`);
consoleErrors.slice(0, 10).forEach((e) => console.log("  " + e));
console.log(`shots in ${OUT}/${LABEL}-*.png`);
console.log(`summary in ${OUT}/${LABEL}.json`);

if (pageErrors.length > 0) {
  process.exit(2);
}
