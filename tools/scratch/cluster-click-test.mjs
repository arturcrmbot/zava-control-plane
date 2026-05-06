/**
 * Test: does clicking on a cluster's screen-space position trigger
 * a camera fly-to? Verifies by snapping before/after and checking the
 * focused cluster name disappears from FAR LOD (other names suppressed).
 */
import { chromium } from "playwright";
import { mkdirSync } from "fs";

const URL = "http://localhost:5175/?view=constellation";
const OUT = "/tmp/cstl-shots";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  viewport: { width: 1600, height: 1000 },
});
const page = await ctx.newPage();

page.on("pageerror", (err) =>
  console.log(`PAGE ERROR: ${err.name}: ${err.message}`),
);

await page.goto(URL, { waitUntil: "domcontentloaded" });
await page.waitForSelector("canvas");
await page.waitForTimeout(4_000);
await page.screenshot({ path: `${OUT}/click-test-01-before.png` });

// Get the canvas bounding box.
const box = await page.locator("canvas").first().boundingBox();
console.log(`canvas box: ${JSON.stringify(box)}`);

// Hit a cluster — pick screen coords above and right of centre, where
// clusters typically sit at overview camera angle.
// Try a position that should hit one of the FAR-LOD clusters in the upper
// portion of the canvas, away from the centre substrate.
const cx = box.x + box.width * 0.72;
const cy = box.y + box.height * 0.30;
console.log(`clicking at (${cx}, ${cy})`);
await page.mouse.click(cx, cy);
await page.waitForTimeout(3_500);
await page.screenshot({ path: `${OUT}/click-test-02-after-click.png` });

// Look at second region too.
await page.mouse.click(box.x + box.width * 0.28, box.y + box.height * 0.45);
await page.waitForTimeout(3_500);
await page.screenshot({ path: `${OUT}/click-test-03-second-click.png` });

await browser.close();
console.log("done — see /tmp/cstl-shots/click-test-*.png");
