import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "@playwright/test";

const output = path.resolve(process.argv[2]);
const screenshots = path.join(output, "screenshots");
const videos = path.join(output, "video");
fs.mkdirSync(screenshots, { recursive: true });
fs.mkdirSync(videos, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  recordVideo: { dir: videos, size: { width: 1440, height: 1000 } },
});
const page = await context.newPage();
const consoleErrors = [];
const pageErrors = [];
page.on("console", message => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", error => pageErrors.push(String(error)));

await page.goto(pathToFileURL(path.join(output, "dashboard.html")).href, {
  waitUntil: "domcontentloaded",
});
await page.locator("#proof-status").waitFor({ state: "visible" });
if ((await page.locator("#proof-status").textContent()) !== "PASS") {
  throw new Error("proof dashboard did not render PASS");
}
if ((await page.locator("[data-workflow-status='PASS']").count()) !== 8) {
  throw new Error("proof dashboard did not render all eight workflows");
}
await page.screenshot({
  path: path.join(screenshots, "fashion-proof-dashboard.png"),
  fullPage: true,
});
const video = page.video();
await page.close();
if (video) {
  await video.saveAs(path.join(videos, "fashion-proof-dashboard.webm"));
}
await context.close();
await browser.close();

const result = {
  status: consoleErrors.length === 0 && pageErrors.length === 0 ? "PASS" : "FAIL",
  console_errors: consoleErrors,
  page_errors: pageErrors,
};
fs.writeFileSync(
  path.join(output, "browser.json"),
  JSON.stringify(result, null, 2) + "\n",
);
if (result.status !== "PASS") process.exit(1);

