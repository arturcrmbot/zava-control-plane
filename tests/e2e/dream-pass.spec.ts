/**
 * Dream-pass end-to-end on the blueprint constellation.
 *
 * Validates the full chain:
 *   1. Backend serves /api/memory/per-persona with a recruiter row
 *      attributed to the hr function (seeded via /api/memory/v2/seed-demo
 *      + organic cadence-loop consolidation).
 *   2. The blueprint constellation page renders the HR planet with a
 *      lesson-count badge ("· N✦") in its label.
 *   3. A subsequent manual dream-pass trigger flips the planet into
 *      a transient "DREAMING" state visible in the label.
 *
 * Pre-requisites — both must be running:
 *   - FastAPI on :3101 (DREAM_PASS_DEMO_CADENCE_SECONDS=180
 *     DREAM_PASS_TRIGGER_BACKLOG=5 MEMORY_DOMAINS=hiring)
 *   - blueprint dev server on :5275 (`npm run dev:blueprint`)
 */
import { test, expect } from "@playwright/test";

const API = process.env.API_BASE_URL || "http://localhost:3101";
const BLUEPRINT = process.env.BLUEPRINT_BASE_URL || "http://localhost:5275";

const SEED = {
  domain: "hiring",
  entries: [
    { role: "recruiter", verdict: "reject", gate: "cv_screen",
      reason: "weak voice", signals: { voice_score: 1.2, cv_score: 2 },
      workflow_id: "W-PWE2E-1" },
    { role: "recruiter", verdict: "reject", gate: "cv_screen",
      reason: "weak voice", signals: { voice_score: 1.4, cv_score: 1 },
      workflow_id: "W-PWE2E-2" },
    { role: "recruiter", verdict: "reject", gate: "cv_screen",
      reason: "weak voice", signals: { voice_score: 1.8, cv_score: 2 },
      workflow_id: "W-PWE2E-3" },
    { role: "recruiter", verdict: "reject", gate: "cv_screen",
      reason: "weak voice", signals: { voice_score: 1.1, cv_score: 3 },
      workflow_id: "W-PWE2E-4" },
    { role: "recruiter", verdict: "reject", gate: "cv_screen",
      reason: "weak voice", signals: { voice_score: 1.5, cv_score: 2 },
      workflow_id: "W-PWE2E-5" },
    { role: "recruiter", verdict: "reject", gate: "cv_screen",
      reason: "weak voice", signals: { voice_score: 1.3, cv_score: 1 },
      workflow_id: "W-PWE2E-6" },
  ],
};

test.describe("dream-pass organic loop", () => {
  test.setTimeout(180_000);

  test("backend: seed → organic trigger → lessons attributed to hr/recruiter", async ({ request }) => {
    const seedR = await request.post(`${API}/api/memory/v2/seed-demo`, { data: SEED });
    expect(seedR.ok()).toBeTruthy();
    const seedBody = await seedR.json();
    expect(seedBody.written).toBe(SEED.entries.length);

    // Also explicitly trigger a pass so the assertion isn't timing-coupled
    // to the cadence loop. The cadence will still cover the organic path
    // separately; the manual trigger guarantees deterministic test timing.
    const trigR = await request.post(`${API}/api/memory/v2/dream`, {
      data: { domain: "hiring" },
    });
    expect(trigR.ok()).toBeTruthy();

    // Poll per-persona for up to 20s for the recruiter row to appear with
    // function_key=hr and lessons > 0.
    let attempt = 0;
    let recruiterRow: any = null;
    while (attempt < 20) {
      const r = await request.get(`${API}/api/memory/per-persona`);
      expect(r.ok()).toBeTruthy();
      const body = await r.json();
      recruiterRow = (body.items || []).find(
        (i: any) => i.persona_role === "recruiter",
      );
      if (recruiterRow && recruiterRow.lessons > 0) break;
      await new Promise(res => setTimeout(res, 1000));
      attempt++;
    }
    expect(recruiterRow, "recruiter row should be present after consolidation").not.toBeNull();
    expect(recruiterRow.function_key).toBe("hr");
    expect(recruiterRow.lessons).toBeGreaterThan(0);
  });

  test("constellation: hr planet shows lesson satellites + count badge", async ({ page }) => {
    // Seed + trigger so the planet definitely has lessons attributed to it.
    await page.request.post(`${API}/api/memory/v2/seed-demo`, { data: SEED });
    await page.request.post(`${API}/api/memory/v2/dream`, { data: { domain: "hiring" } });

    // Wait for backend attribution.
    let recruiterReady = false;
    for (let i = 0; i < 20 && !recruiterReady; i++) {
      const r = await page.request.get(`${API}/api/memory/per-persona`);
      const j = await r.json();
      const row = (j.items || []).find((it: any) =>
        it.persona_role === "recruiter" && it.function_key === "hr" && it.lessons > 0,
      );
      if (row) recruiterReady = true;
      else await page.waitForTimeout(1000);
    }
    expect(recruiterReady, "backend should attribute lessons to hr/recruiter").toBeTruthy();

    // Visit the constellation.
    await page.goto(`${BLUEPRINT}/?view=constellation`, { waitUntil: "domcontentloaded" });

    // Wait for the HR planet's lesson badge (rendered by FunctionPlanets
    // via <Html>; data-testid="fn-hr-lessons"). useLiveMemory polls
    // every 5s so allow up to 12s after mount.
    const badge = page.locator('[data-testid="fn-hr-lessons"]');
    await expect(badge).toBeVisible({ timeout: 15_000 });
    const badgeText = await badge.textContent();
    expect(badgeText).toMatch(/\d+✦/);

    await page.screenshot({
      path: "tests/e2e/screenshots/dream-pass-hr-lessons.png",
      fullPage: true,
    });
  });

  test("constellation: DREAMING pill appears during in-flight pass", async ({ page }) => {
    // Ensure backlog so the pass actually has work to do.
    await page.request.post(`${API}/api/memory/v2/seed-demo`, { data: SEED });

    // Capture browser console + errors for debugging.
    page.on("console", m => {
      if (["log", "warn", "error"].includes(m.type())) {
        // eslint-disable-next-line no-console
        console.log(`[browser:${m.type()}]`, m.text());
      }
    });
    page.on("pageerror", e => console.log("[browser:pageerror]", e.message));

    await page.goto(`${BLUEPRINT}/?view=constellation`, { waitUntil: "domcontentloaded" });

    // Wait for the recruiter row to be present (so domainToFunction is populated).
    await page.waitForFunction(async () => {
      const r = await fetch("/api/memory/per-persona");
      const j = await r.json();
      return (j.items || []).some((it: any) =>
        it.persona_role === "recruiter" && it.function_key === "hr",
      );
    }, { timeout: 10_000 });

    // Wait one more poll cycle to be sure the hook has the d2f mapping.
    await page.waitForTimeout(6000);

    // Fire the pass.
    await page.request.post(`${API}/api/memory/v2/dream`, {
      data: { domain: "hiring" },
    });

    const dreaming = page.locator('[data-testid="fn-hr-dreaming"]');
    await expect(dreaming).toBeVisible({ timeout: 15_000 });

    await page.screenshot({
      path: "tests/e2e/screenshots/dream-pass-dreaming.png",
      fullPage: true,
    });
  });
});
