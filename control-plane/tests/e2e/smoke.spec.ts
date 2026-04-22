import { test, expect, Page } from "@playwright/test";

const API = "http://localhost:3001";

// Routes that must render SOMETHING without JS errors.
const ROUTES = [
  { path: "/fleet", sentinel: /WPP Control Plane|in_progress|Fleet|exceptions|workflows/i },
  { path: "/exceptions", sentinel: /exceptions|Exception Queue|empty|no exceptions/i },
  { path: "/policy", sentinel: /Policy|autonomy|policies/i },
  { path: "/analytics", sentinel: /Analytics|total|completed/i },
  { path: "/evals", sentinel: /Evaluation|eval|results/i },
];

function wireConsoleCapture(page: Page): { errors: string[]; pageErrors: string[] } {
  const errors: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", m => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", e => pageErrors.push(String(e)));
  return { errors, pageErrors };
}

// --- API contract tests -----------------------------------------------------

test.describe("API contract", () => {
  test("workflow shape has camelCase keys the UI reads", async ({ request }) => {
    // Ensure at least one workflow exists.
    const inject = await request.post(`${API}/api/simulator/inject`, {
      data: { scenario: "demo-fail" },
    });
    expect(inject.ok()).toBeTruthy();
    const body = await inject.json();
    const id = body.workflow_id;
    expect(id).toBeTruthy();

    // Give the store a moment.
    await new Promise(r => setTimeout(r, 1500));

    const resp = await request.get(`${API}/api/workflows/${id}`);
    expect(resp.ok()).toBeTruthy();
    const json = await resp.json();
    const w = json.workflow;

    for (const key of [
      "id", "status", "currentPhase", "actionLedger",
      "activeExceptionId", "vendor", "invoice",
      "createdAt", "slaDueAt", "orchestrationInstanceId",
    ]) {
      expect(w, `workflow.${key} should exist`).toHaveProperty(key);
    }
    expect(w.invoice).toHaveProperty("poRef");
    expect(w.invoice).toHaveProperty("lineItems");
    expect(Array.isArray(w.actionLedger)).toBeTruthy();

    // Snake_case variants should NOT appear (would indicate serialization regression).
    expect(w).not.toHaveProperty("current_phase");
    expect(w).not.toHaveProperty("action_ledger");
  });

  test("exceptions list has camelCase keys", async ({ request }) => {
    const resp = await request.get(`${API}/api/exceptions/`);
    expect(resp.ok()).toBeTruthy();
    const list = await resp.json();
    expect(Array.isArray(list)).toBeTruthy();
    if (list.length > 0) {
      const e = list[0];
      for (const key of ["id", "workflowId", "category", "severity", "composedBy", "createdAt"]) {
        expect(e, `exception.${key}`).toHaveProperty(key);
      }
      expect(e).not.toHaveProperty("workflow_id");
      expect(e).not.toHaveProperty("composed_by");
    }
  });
});

// --- UI smoke per route -----------------------------------------------------

test.describe("UI smoke", () => {
  for (const r of ROUTES) {
    test(`renders ${r.path}`, async ({ page }) => {
      const cap = wireConsoleCapture(page);
      await page.goto(r.path, { waitUntil: "domcontentloaded" });
      // Give React a moment to mount + initial fetch to resolve.
      await page.waitForTimeout(2000);

      const body = await page.innerText("body");
      // Blank-page check: if the body has very little content OR lacks our sentinel, fail.
      expect(body.length, `${r.path} body too short (blank page?)`).toBeGreaterThan(40);
      expect(body, `${r.path} should contain expected content`).toMatch(r.sentinel);

      // Console error check — ignore favicon-related noise.
      const realErrors = [...cap.errors, ...cap.pageErrors].filter(
        e => !/favicon\.ico/i.test(e)
      );
      expect(realErrors, `${r.path} console errors`).toEqual([]);
    });
  }

  test("workflow detail page renders for an existing id", async ({ page, request }) => {
    // Pick an existing workflow (or inject one).
    let list = await (await request.get(`${API}/api/workflows/`)).json();
    if (list.length === 0) {
      await request.post(`${API}/api/simulator/inject`, { data: { scenario: "demo-fail" } });
      await new Promise(r => setTimeout(r, 1500));
      list = await (await request.get(`${API}/api/workflows/`)).json();
    }
    expect(list.length).toBeGreaterThan(0);
    const id = list[0].id;

    const cap = wireConsoleCapture(page);
    await page.goto(`/workflows/${id}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const body = await page.innerText("body");
    expect(body.length, `/workflows/${id} blank`).toBeGreaterThan(80);
    // The Overview tab shows "status:" and "phase:" labels.
    expect(body).toMatch(/status|phase|Overview/i);

    const realErrors = [...cap.errors, ...cap.pageErrors].filter(
      e => !/favicon\.ico/i.test(e)
    );
    expect(realErrors, `/workflows/${id} console errors`).toEqual([]);
  });
});

// --- End-to-end pipeline ----------------------------------------------------

// --- Interaction tests that actually click things --------------------------

test.describe("Interactions", () => {
  test("workflow detail: all tabs switch without errors", async ({ page, request }) => {
    // Ensure at least one workflow exists.
    let list = await (await request.get(`${API}/api/workflows/`)).json();
    if (list.length === 0) {
      await request.post(`${API}/api/simulator/inject`, { data: { scenario: "demo-fail" } });
      await new Promise(r => setTimeout(r, 1500));
      list = await (await request.get(`${API}/api/workflows/`)).json();
    }
    const id = list[0].id;
    const cap = wireConsoleCapture(page);
    await page.goto(`/workflows/${id}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Scope tab clicks to the main panel — the right rail has its own
    // "Orchestration" tab which would otherwise match ambiguously.
    const main = page.getByRole("main");
    for (const tabName of ["Overview", "Phases", "Traces", "Ledger", "Amplification", "Orchestration"]) {
      await main.getByRole("button", { name: new RegExp(`^${tabName}$`) }).click();
      await page.waitForTimeout(500);
      const mainBody = await main.innerText();
      expect(mainBody, `${tabName} tab produced no content`).not.toEqual("");
    }
    const realErrors = [...cap.errors, ...cap.pageErrors].filter(e => !/favicon\.ico/i.test(e));
    expect(realErrors).toEqual([]);
  });

  test("exception queue: per-item Approve button resolves and removes the row", async ({ page, request }) => {
    test.setTimeout(180_000);
    // Ensure an exception exists (inject demo-fail and wait).
    let exs = await (await request.get(`${API}/api/exceptions/`)).json();
    if (exs.length === 0) {
      await request.post(`${API}/api/simulator/inject`, { data: { scenario: "demo-fail" } });
      const dead = Date.now() + 120_000;
      while (Date.now() < dead) {
        await new Promise(r => setTimeout(r, 3000));
        exs = await (await request.get(`${API}/api/exceptions/`)).json();
        if (exs.length > 0) break;
      }
    }
    expect(exs.length, "need at least 1 open exception").toBeGreaterThan(0);
    const startCount = exs.length;
    const targetId = exs[0].id;

    const cap = wireConsoleCapture(page);
    await page.goto("/exceptions", { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Expand the first exception card so its per-option buttons are visible.
    const firstHeader = page.locator("button").filter({ hasText: new RegExp(exs[0].workflowId) }).first();
    await firstHeader.click();
    await page.waitForTimeout(300);

    // Click Approve.
    await page.getByTestId("resolve-approve").first().click();
    await page.waitForTimeout(2000);

    // Verify backend: targeted exception should be resolved.
    const after = await (await request.get(`${API}/api/exceptions/`)).json();
    expect(after.length, "total open count must drop by 1").toBeLessThan(startCount);
    expect(after.map((e: { id: string }) => e.id)).not.toContain(targetId);

    const realErrors = [...cap.errors, ...cap.pageErrors].filter(e => !/favicon\.ico/i.test(e));
    expect(realErrors).toEqual([]);
  });
});

test.describe("Pipeline E2E", () => {
  test("demo-fail inject produces deterministic validator-blocked exception", async ({ request }) => {
    test.setTimeout(180_000);  // 3 min — workflow needs to progress through Intake + Validation + Routing

    const inj = await request.post(`${API}/api/simulator/inject`, {
      data: { scenario: "demo-fail" },
    });
    expect(inj.ok()).toBeTruthy();
    const { workflow_id: wid } = await inj.json();

    // Poll exceptions up to 120s.
    const deadline = Date.now() + 150_000;  // 2.5 min — cold intake path can be slow
    let found: { category: string; composedBy: string; severity: string; workflowId: string } | null = null;
    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 3000));
      const list = await (await request.get(`${API}/api/exceptions/`)).json();
      const candidates = list.filter((e: { workflowId: string }) => e.workflowId === wid);
      if (candidates.length > 0) { found = candidates[0]; break; }
    }
    expect(found, `no exception for ${wid} within 120s`).not.toBeNull();
    expect(found!.category).toBe("validator-blocked");
    expect(found!.severity).toBe("high");
    expect(found!.composedBy).toBe("deterministic");
  });
});
