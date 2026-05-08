import { test, expect, Page } from "@playwright/test";

const API = "http://localhost:3001";

// Routes that must render SOMETHING without JS errors.
const ROUTES = [
  { path: "/fleet", sentinel: /Zava Control Plane|in_progress|Fleet|exceptions|workflows/i },
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
    for (const tabName of ["Overview", "Phases", "Traces", "Ledger", "Amplification", "Execution Timeline"]) {
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

// --- Data-population tests (phases, spans, ledger) -------------------------

test.describe("Workflow data population", () => {
  test("after a workflow progresses, phases + spans + ledger are populated", async ({ request }) => {
    test.setTimeout(180_000);
    const inj = await request.post(`${API}/api/simulator/inject`, {
      data: { scenario: "demo-fail" },
    });
    const { workflow_id: wid } = await inj.json();

    // Poll until at least one phase exists.
    const deadline = Date.now() + 150_000;
    let payload: { workflow: { actionLedger: unknown[] }; phases: unknown[]; spans: unknown[] } | null = null;
    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 3000));
      const r = await request.get(`${API}/api/workflows/${wid}`);
      if (!r.ok()) continue;
      const body = await r.json();
      // Require all three to be populated before breaking — spans lag
      // behind phases and the test otherwise races on empty spans.
      if (body.phases?.length > 0 &&
          body.spans?.length > 0 &&
          body.workflow?.actionLedger?.length > 0) { payload = body; break; }
    }
    expect(payload, `phases/spans/ledger never populated for ${wid} within 150s`).not.toBeNull();
    expect(payload!.phases.length, "phases should have at least 1 entry").toBeGreaterThan(0);
    expect(payload!.workflow.actionLedger.length, "ledger should have at least 1 entry").toBeGreaterThan(0);
    expect(payload!.spans.length, "spans should have at least 1 entry").toBeGreaterThan(0);
  });
});

test.describe("Pipeline E2E", () => {
  test("demo-fail inject produces deterministic validator-blocked exception", async ({ request }) => {
    test.setTimeout(360_000);  // 6 min — stack is often backed up with prior workflows

    const inj = await request.post(`${API}/api/simulator/inject`, {
      data: { scenario: "demo-fail" },
    });
    expect(inj.ok()).toBeTruthy();
    const { workflow_id: wid } = await inj.json();

    const deadline = Date.now() + 300_000;  // 5 min — tolerate a backed-up stack
    let found: { category: string; composedBy: string; severity: string; workflowId: string } | null = null;
    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 3000));
      const list = await (await request.get(`${API}/api/exceptions/`)).json();
      const candidates = list.filter((e: { workflowId: string }) => e.workflowId === wid);
      if (candidates.length > 0) { found = candidates[0]; break; }
    }
    expect(found, `no exception for ${wid} within 5min`).not.toBeNull();
    expect(found!.category).toBe("validator-blocked");
    expect(found!.severity).toBe("high");
    // Accept any valid composed_by — Fleet Manager may augment the
    // deterministic exception before the test polls it, which is correct behaviour.
    expect(["deterministic", "fleet-manager", "fleet-manager-augmented"])
      .toContain(found!.composedBy);
  });
});

// --- Apex redesign tests ----------------------------------------------------

test.describe("Apex API contract", () => {
  test("workflow detail carries mcpCalls, economics, narrative when exception present", async ({ request }) => {
    test.setTimeout(180_000);
    const inj = await request.post(`${API}/api/simulator/inject`, {
      data: { scenario: "demo-fail" },
    });
    const { workflow_id: wid } = await inj.json();
    const deadline = Date.now() + 150_000;
    let body: any = null;
    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 3000));
      const r = await request.get(`${API}/api/workflows/${wid}`);
      if (!r.ok()) continue;
      body = await r.json();
      if (body.economics && (body.narrative || body.activeException === null)) break;
    }
    expect(body).not.toBeNull();
    expect(body.economics).toBeTruthy();
    for (const k of ["computeCostUsd", "modelCalls", "toolCalls", "daysElapsed", "slaToken"]) {
      expect(body.economics).toHaveProperty(k);
    }
    expect(Array.isArray(body.mcpCalls)).toBeTruthy();
    if (body.activeException) {
      expect(body.narrative).toBeTruthy();
      for (const k of ["whatHappened", "whatAgentTried", "agentRecommendation"]) {
        expect(body.narrative).toHaveProperty(k);
      }
    }
  });

  test("fleet economics endpoint returns rollup", async ({ request }) => {
    const r = await request.get(`${API}/api/fleet/economics`);
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    for (const k of ["activeWorkflowCount", "totalComputeCostUsd",
                     "totalModelCalls", "totalToolCalls", "averageCostPerWorkflow"]) {
      expect(body).toHaveProperty(k);
    }
  });

  test("exception options carry a recommended action", async ({ request }) => {
    const r = await request.get(`${API}/api/exceptions/`);
    const list = await r.json();
    if (list.length > 0) {
      expect(list[0].options.some((o: any) => o.recommended === true)).toBeTruthy();
    }
  });
});

test.describe("Apex UI smoke", () => {
  test("/fleet renders KPI tiles + exceptions block", async ({ page }) => {
    await page.goto("/fleet", { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    await expect(page.getByTestId("kpi-tile-row")).toBeVisible();
    await expect(page.getByText(/Exceptions Requiring Attention/i)).toBeVisible();
  });

  test("workflow detail shows Apex widgets", async ({ page, request }) => {
    test.setTimeout(180_000);
    let list = await (await request.get(`${API}/api/workflows/`)).json();
    if (list.length === 0) {
      await request.post(`${API}/api/simulator/inject`, { data: { scenario: "demo-fail" } });
      const deadline = Date.now() + 30_000;
      while (Date.now() < deadline && list.length === 0) {
        await new Promise(r => setTimeout(r, 2000));
        list = await (await request.get(`${API}/api/workflows/`)).json();
      }
    }
    expect(list.length).toBeGreaterThan(0);
    const id = list[0].id;
    await page.goto(`/workflows/${id}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    for (const tid of ["workflow-header-tiles", "phase-ribbon", "economics-panel",
                       "fleet-assignment", "audit-trail"]) {
      await expect(page.getByTestId(tid)).toBeVisible();
    }
  });

  test("execution timeline shows MCP steps after the workflow progresses", async ({ page, request }) => {
    test.setTimeout(300_000);  // 5 min — MCP calls happen in Routing which comes after Intake + Validation
    // Accept ANY workflow that has mcpCalls (not just the one we just injected)
    // — on a busy stack, an older workflow reaches Routing before a fresh one.
    const deadline = Date.now() + 240_000;
    let wid: string | null = null;
    let body: any = null;
    await request.post(`${API}/api/simulator/inject`, { data: { scenario: "demo-fail" } });
    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 3000));
      const list = await (await request.get(`${API}/api/workflows/`)).json();
      for (const w of list) {
        const r = await request.get(`${API}/api/workflows/${w.id}`);
        if (!r.ok()) continue;
        const b = await r.json();
        if (b.mcpCalls && b.mcpCalls.length > 0) { wid = w.id; body = b; break; }
      }
      if (wid) break;
    }
    expect(wid, "no workflow progressed far enough to produce MCP calls within 4min").not.toBeNull();
    expect(body?.mcpCalls?.length ?? 0).toBeGreaterThan(0);
    await page.goto(`/workflows/${wid}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    await page.getByRole("main").getByRole("button", { name: /^Execution Timeline$/ }).click();
    await page.waitForTimeout(500);
    await expect(page.getByTestId("execution-timeline")).toBeVisible();
    await expect(page.getByTestId("timeline-step-0")).toBeVisible();
    await page.getByTestId("timeline-step-0").click();
    await expect(page.getByTestId("api-configuration")).toContainText(/Request/i);
  });

  test("intervention protocols: clicking recommended action resolves exception", async ({ page, request }) => {
    test.setTimeout(180_000);
    let exs = await (await request.get(`${API}/api/exceptions/`)).json();
    if (exs.length === 0) {
      await request.post(`${API}/api/simulator/inject`, { data: { scenario: "demo-fail" } });
      const deadline = Date.now() + 150_000;
      while (Date.now() < deadline) {
        await new Promise(r => setTimeout(r, 3000));
        exs = await (await request.get(`${API}/api/exceptions/`)).json();
        if (exs.length > 0) break;
      }
    }
    expect(exs.length).toBeGreaterThan(0);
    // Find a workflow whose *active* exception (what the UI renders) has a
    // recommended option. The /exceptions list returns all open ones including
    // older shadowed records; only the workflow's activeException is what the
    // Intervention Protocols component mounts.
    let wid: string | null = null;
    let startId: string | null = null;
    let recommended: string | null = null;
    for (const cand of exs) {
      const r = await request.get(`${API}/api/workflows/${cand.workflowId}`);
      if (!r.ok()) continue;
      const body = await r.json();
      const act = body.activeException;
      const rec = act?.options?.find((o: any) => o.recommended)?.action;
      if (act && rec) {
        wid = cand.workflowId;
        startId = act.id;
        recommended = rec;
        break;
      }
    }
    expect(wid, "no workflow exposes an active exception with a recommended option").not.toBeNull();
    await page.goto(`/workflows/${wid}`, { waitUntil: "domcontentloaded" });
    await page.getByTestId(`protocol-${recommended}`).waitFor({ state: "visible", timeout: 20_000 });
    await page.getByTestId(`protocol-${recommended}`).click();
    await page.waitForTimeout(2000);
    const after = await (await request.get(`${API}/api/exceptions/`)).json();
    expect(after.map((e: any) => e.id)).not.toContain(startId);
  });
});
