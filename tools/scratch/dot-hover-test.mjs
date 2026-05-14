/**
 * Hover the substrate sphere with the mouse and snap — verifies the
 * dot tooltip + the centre label render together.
 */
import { chromium } from "playwright";
import { mkdirSync } from "fs";

const URL = "http://localhost:5175/?view=constellation";
const OUT = "/tmp/cstl-shots";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();

page.on("pageerror", (err) =>
  console.log(`PAGE ERROR: ${err.name}: ${err.message}`),
);

await page.goto(URL, { waitUntil: "domcontentloaded" });
await page.waitForSelector("canvas");
await page.waitForTimeout(4_000);

// The substrate is at scene origin. From the default camera (0,3,22) it
// projects roughly to canvas centre. Try a sweep of points around centre
// to land on a real dot rather than a filler.
const centerX = 800;
const centerY = 480;

for (let i = 0; i < 12; i++) {
  // Spiral outward from centre.
  const r = 30 + i * 12;
  const a = i * 0.7;
  const x = centerX + Math.cos(a) * r;
  const y = centerY + Math.sin(a) * r;
  await page.mouse.move(x, y);
  await page.waitForTimeout(200);
  const tooltip = await page
    .$eval(".constellation__dot-tooltip", (el) => el.textContent.trim())
    .catch(() => null);
  if (tooltip) {
    console.log(`hit at (${x.toFixed(0)},${y.toFixed(0)}): ${tooltip}`);
    await page.screenshot({ path: `${OUT}/dot-tooltip-hit.png` });
    break;
  }
}

await page.screenshot({ path: `${OUT}/dot-tooltip-final.png` });

await browser.close();
console.log("done");
