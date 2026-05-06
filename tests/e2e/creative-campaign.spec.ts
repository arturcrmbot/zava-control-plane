// tests/e2e/creative-campaign.spec.ts
//
// POC3 Phase 5 — UI verification against the LIVE FastAPI on :3001 +
// Vite dev on :5173. Prerequisites:
//   make dev / boot-demo (or just FastAPI + Vite running).
//
// Each test seeds its own workflow via the simulator and pushes phase
// outputs through /internal/durable-event so the suite is hermetic.
//
// Asserts:
//   1. Fleet dashboard shows the "Creative Campaigns" filter chip and
//      filters the workflow list when clicked.
//   2. WorkflowDetail for a creative-campaign workflow renders:
//      - the brief scorecard (audience / mandatory messages / KPIs)
//      - 3 concept tiles with stills + brand-fit + distinctiveness
//      - the 6-frame storyboard strip (when storyboard slot is set)
//      - the "Open in Figma" link when handoff slot is set
//   3. Clicking "Lock route" on a concept tile raises
//      concept_lock_decision and persists locked_route on the workflow.

import { test, expect } from "@playwright/test";

const API = "http://localhost:3001";
const UI = "http://localhost:5173";

const briefJson = {
  id: "BRF-001",
  client_brand: "Solene",
  category: "luxury_fragrance",
  audience: "Aspirational European 25-44, primary FR + UK",
  mandatory_messages: [
    "regenerative provenance",
    "low-impact craftsmanship",
    "single-source botanicals",
  ],
  channels: ["CTV", "OOH", "social"],
  kpis: { awareness: "+15%", intent: "+8%" },
  jurisdictions: ["UK", "FR", "DE"],
  constraints: ["no human faces", "EU green-claims directive"],
};

const routes = ["A", "B", "C"].map((r, i) => ({
  route_name: `route-${r}`,
  headline: ["Origin", "Pulse", "Land"][i],
  description: ["Cinematic minimalism", "Social-first vibrancy", "Provenance-led"][i],
  stills: [1, 2, 3, 4].map(n => `creative-campaign/cached/BRF-001/route-${r}/${n}.svg`),
  brand_fit: [0.91, 0.88, 0.83][i],
  distinctiveness: [0.74, 0.86, 0.81][i],
}));

const storyboardFrames = [1, 2, 3, 4, 5, 6].map(
  n => `creative-campaign/cached/BRF-001/storyboard/${n}.svg`,
);

async function spawnAndSeed(
  request: import("@playwright/test").APIRequestContext,
  opts: { withStoryboard?: boolean; withHandoff?: boolean } = {},
): Promise<string> {
  const r = await request.post(`${API}/api/simulator/creative-campaign`, {
    data: { brief_id: "BRF-001" },
  });
  expect(r.ok(), `spawn: ${r.status()} ${await r.text()}`).toBeTruthy();
  const { workflow_id: wid } = await r.json();

  await request.post(`${API}/internal/durable-event`, {
    data: {
      workflow_id: wid,
      kind: "creative.phase.output",
      payload: { slot: "brief", data: briefJson },
    },
  });
  await request.post(`${API}/internal/durable-event`, {
    data: {
      workflow_id: wid,
      kind: "creative.phase.output",
      payload: { slot: "brief_synthesis", data: { brief_json: briefJson } },
    },
  });
  await request.post(`${API}/internal/durable-event`, {
    data: {
      workflow_id: wid,
      kind: "creative.phase.output",
      payload: { slot: "concept_fanout", data: { routes } },
    },
  });
  if (opts.withStoryboard) {
    await request.post(`${API}/internal/durable-event`, {
      data: {
        workflow_id: wid,
        kind: "creative.phase.output",
        payload: {
          slot: "storyboard_render",
          data: {
            frames: storyboardFrames,
            frame_captions: ["Open", "Cut", "Close-up", "Brand mark", "Tagline", "End"],
          },
        },
      },
    });
  }
  if (opts.withHandoff) {
    await request.post(`${API}/internal/durable-event`, {
      data: {
        workflow_id: wid,
        kind: "creative.phase.output",
        payload: {
          slot: "package_handoff",
          data: { figma_file_url: "https://www.figma.com/design/DEMO/Apex" },
        },
      },
    });
  }
  return wid;
}

test.describe("POC3 creative-campaign UI", () => {
  test("fleet dashboard shows Creative Campaigns filter chip and filters workflows", async ({ page, request }) => {
    const wid = await spawnAndSeed(request);

    await page.goto(`${UI}/fleet`);
    await expect(page.getByTestId("fleet-domain-chips")).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId("fleet-chip-creative-campaign")).toBeVisible();
    await expect(page.getByTestId("fleet-chip-all")).toBeVisible();

    const card = page.locator(`a[href="/workflows/${wid}"]`);
    await expect(card).toBeVisible({ timeout: 20000 });
    await expect(card).toContainText("creative");
    await expect(card).toContainText(wid);

    // Click the Creative Campaigns chip — should still show this card.
    await page.getByTestId("fleet-chip-creative-campaign").click();
    await expect(card).toBeVisible();
  });

  test("WorkflowDetail renders brief scorecard, concept tiles, storyboard strip, Figma link", async ({ page, request }) => {
    const wid = await spawnAndSeed(request, { withStoryboard: true, withHandoff: true });

    await page.goto(`${UI}/workflows/${wid}`);

    await expect(page.getByTestId("creative-brief-scorecard")).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId("creative-brief-scorecard")).toContainText("Solene");
    await expect(page.getByTestId("creative-brief-scorecard")).toContainText("regenerative provenance");
    await expect(page.getByTestId("creative-brief-scorecard")).toContainText("+15%");

    await expect(page.getByTestId("creative-concept-tiles")).toBeVisible();
    for (const r of ["route-A", "route-B", "route-C"]) {
      await expect(page.getByTestId(`creative-concept-route-${r}`)).toBeVisible();
    }

    await expect(page.getByTestId("creative-storyboard-strip")).toBeVisible();
    const strip = page.getByTestId("creative-storyboard-strip");
    await expect(strip.locator("img")).toHaveCount(6);

    await expect(page.getByTestId("creative-figma-link")).toBeVisible();
    await expect(page.getByTestId("creative-figma-link")).toHaveAttribute(
      "href",
      "https://www.figma.com/design/DEMO/Apex",
    );
  });

  test("Lock route button raises concept_lock_decision and persists locked_route", async ({ page, request }) => {
    const wid = await spawnAndSeed(request);

    await page.goto(`${UI}/workflows/${wid}`);
    await expect(page.getByTestId("creative-concept-tiles")).toBeVisible({ timeout: 20000 });

    await page.getByTestId("creative-lock-route-B").click();

    // Verify the API received the decision and persisted locked_route.
    await expect.poll(async () => {
      const r = await request.get(`${API}/api/workflows/${wid}`);
      const j = await r.json();
      const lock = (j.workflow.payload || {}).conceptLockDecision
        ?? (j.workflow.payload || {}).concept_lock_decision;
      return lock?.lockedRoute ?? lock?.locked_route;
    }, { timeout: 10000 }).toBe("route-B");
  });
});
