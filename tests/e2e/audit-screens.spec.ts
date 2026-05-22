/**
 * Screenshot every route in the control plane (port 5273) at desktop +
 * narrow widths so we can see what's cluttered and what needs trimming.
 * Output: tests/e2e/screenshots/audit/<route>-<viewport>.png
 *
 * Also pre-seeds some workflows so the screens aren't blank.
 */
import { test } from "@playwright/test";

const UI = process.env.UI_BASE_URL || "http://localhost:5273";
const API = process.env.API_BASE_URL || "http://localhost:3101";

const ROUTES = [
  "/",
  "/dashboard",
  "/memory",
  "/knowledge",
  "/analytics",
  "/evals",
  "/economics",
  "/policy",
];

test.describe.serial("audit screenshots", () => {
  test("seed some workflows + memories", async ({ request }) => {
    // Trigger a couple of injections so the feed isn't empty
    for (const scenario of ["demo-fail", "demo-fail", "demo-fail"]) {
      try {
        await request.post(`${API}/api/simulator/inject`, { data: { scenario } });
      } catch {}
    }
    // Seed memories so /memory has content
    try {
      await request.post(`${API}/api/memory/v2/seed-demo`, {
        data: {
          domain: "hiring",
          entries: Array.from({ length: 6 }, (_, i) => ({
            role: "recruiter", verdict: "reject", gate: "cv_screen",
            reason: "weak voice", signals: { voice_score: 1 + i * 0.2, cv_score: 2 },
            workflow_id: `W-AUDIT-${i}`,
          })),
        },
      });
    } catch {}
  });

  for (const route of ROUTES) {
    test(`screenshot ${route}`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", e => errors.push(String(e)));
      page.on("console", m => {
        if (m.type() === "error") errors.push(`[console] ${m.text()}`);
      });

      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(`${UI}${route}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(2500);

      const slug = route === "/" ? "root" : route.replace(/\//g, "-").replace(/^-/, "");
      await page.screenshot({
        path: `tests/e2e/screenshots/audit/${slug}-1440.png`,
        fullPage: true,
      });

      if (errors.length) {
        console.log(`[errors on ${route}]`, errors.slice(0, 5));
      }
    });
  }

  test("screenshot a workflow drill-in", async ({ page, request }) => {
    // Find a workflow id we can drill into
    let id: string | null = null;
    for (let i = 0; i < 10; i++) {
      const r = await request.get(`${API}/api/workflows`);
      if (r.ok()) {
        const j = await r.json();
        const items = j.items ?? j.workflows ?? j;
        const first = Array.isArray(items) && items.length > 0 ? items[0] : null;
        id = first?.id ?? first?.workflow_id ?? null;
        if (id) break;
      }
      await new Promise(r => setTimeout(r, 1500));
    }
    if (!id) {
      console.log("[audit] no workflow id available");
      return;
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${UI}/workflows/${id}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    await page.screenshot({
      path: `tests/e2e/screenshots/audit/workflow-detail-1440.png`,
      fullPage: true,
    });
  });
});
