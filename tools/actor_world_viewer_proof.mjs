// tools/actor_world_viewer_proof.mjs
//
// Browser assertion driver for the Observable World Viewer (Plan
// 2026-07-13-observable-world-viewer, Task 4). It drives an ALREADY-RUNNING
// real stack booted by tools/actor_world_viewer_proof.sh — no mocks:
//
//   * Control Plane Vite (:5273) serving /world, proxying /api → FastAPI
//   * FastAPI (:3101) hosting the live ActorWorldService (ZAVA_WORLD=support)
//   * Azure Durable Functions host (:7071) with SurgeStaffingOrchestrator
//
// It proves the viewer renders the REAL actor world end to end, using DOM
// locators/test-ids cross-checked against the JSON journal and the Durable
// runtime — never screenshot-only judgement:
//
//   1. /world loads; the baseline support + reserve worker IDs from the live
//      snapshot are visible as chips, and baseline ticket cards appear.
//   2. Click "Inject demand surge".
//   3. The WAITING lane accumulates genuinely NEW ticket IDs (not just a
//      bigger count) versus baseline.
//   4. The Durable intervention strip appears and shows one stable journal
//      trace across the intervention and reallocation steps.
//   5. The worker.reallocated IDs from /api/world/events equal the Durable
//      output command's worker IDs (queried on :7071) equal the last_response
//      command IDs equal the worker chips that newly appear in the SUPPORT
//      group in the DOM (and vanish from RESERVE).
//   6. A ticket.resolved lands AFTER command.accepted — the world keeps
//      running post-intervention — and a resolved card is visible.
//   7. No aggregate WorldSignalsPanel survives (static deletion check — no
//      extra process booted).
//
// Screenshots (baseline/pressure/intervention/reallocated/resolved) and a
// session video are written under tmp/actor-world-viewer-proof/ as evidence
// alongside the machine-checked summary.json. Every wait has a bounded
// deadline; any mismatch throws and the process exits non-zero.
import { chromium } from "playwright";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const UI_BASE = (process.env.WORLD_UI_BASE || "http://127.0.0.1:5273").replace(/\/$/, "");
const API_BASE = (process.env.WORLD_API_BASE || "http://127.0.0.1:3101").replace(/\/$/, "");
const FUNC_BASE = (process.env.FUNCTIONS_HOST || "http://127.0.0.1:7071").replace(/\/$/, "");
const TASK_HUB = process.env.WORLD_TASK_HUB || "InvoiceP2PHub";
const OUT_DIR = process.env.PROOF_OUT_DIR || "tmp/actor-world-viewer-proof";
const REPO_ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");

// Bounded wall-clock deadlines (ms). The live sim runs ~480 sim-min at
// 10 min/s ≈ 48 wall-s, so these are generous but finite.
const NAV_DEADLINE = 30_000;
const BASELINE_TICKETS_DEADLINE = 30_000;
const ACCUMULATE_DEADLINE = 90_000;
const CHAIN_DEADLINE = 120_000;
const DOM_DEADLINE = 30_000;
const RESOLVE_DEADLINE = 60_000;
const DURABLE_DEADLINE = 30_000;
const POLL_MS = 500;

const REQUIRED_TYPES = [
  "sensor.tripped",
  "objective.opened",
  "objective.claimed",
  "responder.requested",
  "objective.acting",
  "responder.decided",
  "command.accepted",
  "objective.evaluating",
  "worker.reallocated",
];

class ProofError extends Error {}

function require(condition, message) {
  if (!condition) throw new ProofError(message);
}

const startedAt = Date.now();
const timeline = [];
function mark(step, extra = {}) {
  timeline.push({ t: +((Date.now() - startedAt) / 1000).toFixed(3), step, ...extra });
}

function ensureOut() {
  mkdirSync(OUT_DIR, { recursive: true });
}
function write(name, data) {
  ensureOut();
  writeFileSync(path.join(OUT_DIR, name), JSON.stringify(data, null, 2), "utf-8");
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Poll `fn` until it returns a truthy value or the deadline elapses.
async function waitFor(fn, { deadline, message, interval = POLL_MS }) {
  const end = Date.now() + deadline;
  let lastErr = null;
  for (;;) {
    try {
      const value = await fn();
      if (value) return value;
    } catch (err) {
      lastErr = err;
    }
    if (Date.now() >= end) {
      const suffix = lastErr ? ` (last error: ${lastErr.message})` : "";
      throw new ProofError(`${message} within ${(deadline / 1000).toFixed(0)}s${suffix}`);
    }
    await sleep(interval);
  }
}

const sortedUnique = (xs) => [...new Set(xs)].sort();
const setEqual = (a, b) => {
  const sa = sortedUnique(a);
  const sb = sortedUnique(b);
  return sa.length === sb.length && sa.every((x, i) => x === sb[i]);
};
const subset = (a, b) => {
  const sb = new Set(b);
  return a.every((x) => sb.has(x));
};
const disjoint = (a, b) => {
  const sb = new Set(b);
  return a.every((x) => !sb.has(x));
};

// Durable status fields (input/output) arrive as an object or a JSON string.
function asObj(value) {
  if (typeof value === "string") {
    try {
      return JSON.parse(value);
    } catch {
      return value;
    }
  }
  return value;
}

async function getJson(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`HTTP ${resp.status} for ${url}`);
  return resp.json();
}

// --- journal accumulation (dedupe by seq, moving cursor) --------------------

class Journal {
  constructor() {
    this.bySeq = new Map();
    this.cursor = 0;
  }
  async drain() {
    const body = await getJson(`${API_BASE}/api/world/events?after=${this.cursor}`);
    require(body.enabled === true, "actor-world /events reported disabled");
    for (const ev of body.events || []) this.bySeq.set(Number(ev.seq), ev);
    if (typeof body.latest_seq === "number") {
      this.cursor = Math.max(this.cursor, body.latest_seq);
    }
    if (this.bySeq.size) this.cursor = Math.max(this.cursor, ...this.bySeq.keys());
  }
  all() {
    return [...this.bySeq.keys()].sort((a, b) => a - b).map((s) => this.bySeq.get(s));
  }
  byType(type, trace = null) {
    return this.all().filter((e) => e.type === type && (trace === null || e.trace_id === trace));
  }
  types() {
    return new Set(this.all().map((e) => e.type));
  }
}

// --- DOM readers ------------------------------------------------------------

async function groupWorkerIds(page, groupTestId) {
  return page
    .locator(`[data-testid="${groupTestId}"] [data-testid^="worker-"]`)
    .evaluateAll((els) => els.map((e) => e.getAttribute("data-testid").replace("worker-", "")));
}
async function laneTicketIds(page, laneTestId) {
  return page
    .locator(`[data-testid="${laneTestId}"] [data-testid^="ticket-"]`)
    .evaluateAll((els) => els.map((e) => e.getAttribute("data-testid").replace("ticket-", "")));
}
async function interventionTrace(page) {
  const strip = page.getByTestId("intervention");
  if ((await strip.count()) === 0) return null;
  return (await strip.locator("button").first().innerText()).trim();
}
async function interventionText(page) {
  const strip = page.getByTestId("intervention");
  if ((await strip.count()) === 0) return "";
  return strip.innerText();
}

async function fetchDurableCompleted(instanceId) {
  const url =
    `${FUNC_BASE}/runtime/webhooks/durabletask/instances/${instanceId}` +
    `?taskHub=${TASK_HUB}&connection=Storage&showHistory=false`;
  return waitFor(
    async () => {
      const resp = await fetch(url);
      if (resp.status !== 200) return null;
      const data = await resp.json();
      const status = data.runtimeStatus;
      if (status === "Completed") return data;
      if (["Failed", "Terminated", "Canceled"].includes(status)) {
        throw new ProofError(`Durable instance ${instanceId} ended ${status}: ${data.output}`);
      }
      return null;
    },
    { deadline: DURABLE_DEADLINE, message: `Durable instance ${instanceId} not Completed` },
  );
}

// --- static WorldSignalsPanel deletion check (no extra process) -------------

function assertNoWorldSignalsPanel() {
  const gone = [
    "web/blueprint/src/components/cosmicLens/HUD/WorldSignalsPanel.tsx",
    "web/blueprint/src/components/cosmicLens/HUD/__tests__/WorldSignalsPanel.test.tsx",
  ];
  for (const rel of gone) {
    require(!existsSync(path.join(REPO_ROOT, rel)), `WorldSignalsPanel artefact still present: ${rel}`);
  }
  const lens = path.join(REPO_ROOT, "web/blueprint/src/components/cosmicLens/CosmicLens.tsx");
  if (existsSync(lens)) {
    const src = readFileSync(lens, "utf-8");
    require(!/WorldSignalsPanel/.test(src), "CosmicLens.tsx still references WorldSignalsPanel");
  }
  return { deleted: gone, verified: true };
}

// ---------------------------------------------------------------------------

async function run() {
  ensureOut();
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    recordVideo: { dir: path.join(OUT_DIR, "video"), size: { width: 1600, height: 1000 } },
  });
  const page = await context.newPage();

  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", (m) => {
    if (m.type() === "error" && !/favicon\.ico/i.test(m.text())) consoleErrors.push(m.text());
  });
  page.on("pageerror", (e) => pageErrors.push(String(e)));

  const shot = (name) => page.screenshot({ path: path.join(OUT_DIR, name), fullPage: true });
  const journal = new Journal();
  const summary = { result: "PENDING" };

  try {
    // 1. Load /world -------------------------------------------------------
    await page.goto(`${UI_BASE}/world`, { waitUntil: "domcontentloaded", timeout: NAV_DEADLINE });
    await page.getByTestId("world-route").waitFor({ state: "visible", timeout: NAV_DEADLINE });
    require((await page.getByTestId("world-disabled").count()) === 0, "world route reports the simulator DISABLED");
    mark("world_route_loaded");

    // Baseline snapshot (authoritative) + cursor anchor.
    const baseline = await getJson(`${API_BASE}/api/world/state`);
    require(baseline.enabled === true, "world not enabled at baseline");
    require(baseline.scenario === "support", `baseline scenario is not 'support' (${baseline.scenario})`);
    const baselineReserve = sortedUnique(
      (baseline.workers || []).filter((w) => w.team_id === "TEAM-RESERVE").map((w) => w.id),
    );
    const baselineSupport = sortedUnique(
      (baseline.workers || []).filter((w) => w.team_id === "TEAM-SUPPORT").map((w) => w.id),
    );
    const baselineSeq = Number(baseline.latest_seq);
    require(baselineReserve.length > 0, "baseline snapshot has no TEAM-RESERVE workers");
    require(baselineSupport.length > 0, "baseline snapshot has no TEAM-SUPPORT workers");
    write("baseline.json", baseline);

    // 2. Baseline worker IDs visible as chips in their groups --------------
    await waitFor(
      async () => {
        const support = await groupWorkerIds(page, "workers-support");
        const reserve = await groupWorkerIds(page, "workers-reserve");
        return subset(baselineReserve, reserve) && subset(baselineSupport, support);
      },
      { deadline: DOM_DEADLINE, message: "baseline support/reserve worker chips never all rendered" },
    );
    mark("baseline_workers_visible", {
      reserve: baselineReserve,
      support_count: baselineSupport.length,
    });

    // 3. Baseline ticket cards eventually visible --------------------------
    await waitFor(
      async () => (await page.locator('[data-testid^="ticket-"]').count()) > 0,
      { deadline: BASELINE_TICKETS_DEADLINE, message: "no baseline ticket cards rendered" },
    );
    const baselineWaiting = sortedUnique(await laneTicketIds(page, "lane-waiting"));
    mark("baseline_tickets_visible", { waiting_count: baselineWaiting.length });
    await shot("baseline.png");

    // 4. Click "Inject demand surge" --------------------------------------
    const surgeBtn = page.getByTestId("inject-surge");
    require(!(await surgeBtn.isDisabled()), "inject-surge control is disabled at baseline");
    await surgeBtn.click();
    mark("inject_demand_surge_clicked");

    // 5. WAITING lane accumulates genuinely NEW ticket IDs ----------------
    const accumulation = await waitFor(
      async () => {
        const current = sortedUnique(await laneTicketIds(page, "lane-waiting"));
        const fresh = current.filter((id) => !baselineWaiting.includes(id));
        if (current.length > baselineWaiting.length && fresh.length >= 3) {
          return { current, fresh };
        }
        return null;
      },
      { deadline: ACCUMULATE_DEADLINE, message: "WAITING lane never accumulated new ticket cards after surge" },
    );
    mark("waiting_accumulated", {
      baseline: baselineWaiting.length,
      pressure: accumulation.current.length,
      new_sample: accumulation.fresh.slice(0, 8),
    });
    await shot("pressure.png");

    // 6. Intervention strip appears; capture its trace (step A) -----------
    await page.getByTestId("intervention").waitFor({ state: "visible", timeout: CHAIN_DEADLINE });
    const traceAtIntervention = await interventionTrace(page);
    require(Boolean(traceAtIntervention), "intervention strip rendered no trace id");
    mark("intervention_visible", { trace: traceAtIntervention });
    await shot("intervention.png");

    // Poll the causal journal until the whole required chain exists.
    await waitFor(
      async () => {
        await journal.drain();
        const missing = REQUIRED_TYPES.filter((t) => !journal.types().has(t));
        return missing.length === 0;
      },
      { deadline: CHAIN_DEADLINE, message: "causal chain never completed in the journal" },
    );

    // Anchor on the authoritative Durable response (the applied command).
    const finalState = await waitFor(
      async () => {
        const st = await getJson(`${API_BASE}/api/world/state`);
        return st.last_response && st.last_response.instance_id ? st : null;
      },
      { deadline: DURABLE_DEADLINE, message: "world state never exposed a Durable last_response.instance_id" },
    );
    const lastResponse = finalState.last_response;
    const instanceId = String(lastResponse.instance_id);
    const anchorTrace = String((lastResponse.command || {}).trace_id || "");
    require(Boolean(anchorTrace), "last_response command carried no trace_id");
    const lastRespWorkerIds = sortedUnique(((lastResponse.command || {}).payload || {}).worker_ids || []);

    // Ensure the anchored trace carries the full chain.
    await waitFor(
      async () => {
        await journal.drain();
        const have = new Set(journal.all().filter((e) => e.trace_id === anchorTrace).map((e) => e.type));
        return REQUIRED_TYPES.every((t) => have.has(t));
      },
      { deadline: DURABLE_DEADLINE, message: `anchored trace ${anchorTrace} never carried the full chain` },
    );

    // The objective lifecycle rides the same anchored trace, strictly ordered
    // open -> claimed -> acting -> evaluating, all naming one objective id.
    const objectiveChain = ["objective.opened", "objective.claimed", "objective.acting", "objective.evaluating"];
    const objectiveSteps = objectiveChain.map((type) => {
      const hits = journal.byType(type, anchorTrace).sort((a, b) => a.seq - b.seq);
      require(hits.length > 0, `anchored trace ${anchorTrace} missing ${type}`);
      return { type, seq: hits[0].seq, objective_id: (hits[0].payload || {}).id };
    });
    for (let i = 1; i < objectiveSteps.length; i++) {
      require(
        objectiveSteps[i].seq > objectiveSteps[i - 1].seq,
        `objective lifecycle out of order: ${objectiveSteps[i - 1].type} !< ${objectiveSteps[i].type}`,
      );
    }
    const objectiveId = objectiveSteps[0].objective_id;
    require(
      Boolean(objectiveId) && objectiveSteps.every((s) => s.objective_id === objectiveId),
      `objective id not stable across lifecycle: ${JSON.stringify(objectiveSteps.map((s) => s.objective_id))}`,
    );
    mark("objective_lifecycle", {
      trace: anchorTrace,
      objective_id: objectiveId,
      chain: objectiveSteps.map((s) => `${s.type}@${s.seq}`),
    });
    const accepted = journal.byType("command.accepted", anchorTrace).sort((a, b) => a.seq - b.seq);
    const reallocated = journal.byType("worker.reallocated", anchorTrace);
    const reallocatedIds = sortedUnique(reallocated.map((e) => e.actor_id).filter(Boolean));
    require(reallocatedIds.length > 0, `no worker.reallocated actors for trace ${anchorTrace}`);
    require(
      subset(reallocatedIds, baselineReserve),
      `reallocated ${JSON.stringify(reallocatedIds)} were not all baseline reserve ${JSON.stringify(baselineReserve)}`,
    );
    const commandAcceptedSeq = accepted[0].seq;

    // The UI strip must show the SAME journal trace it started with, and that
    // trace must be the anchored one that backs the reallocation.
    require(
      traceAtIntervention === anchorTrace,
      `intervention strip trace ${traceAtIntervention} != anchored journal trace ${anchorTrace}`,
    );

    // Durable runtime cross-check on :7071 — independent of the API.
    const durable = await fetchDurableCompleted(instanceId);
    write("durable-instance.json", durable);
    const durableOutput = asObj(durable.output) || {};
    const durableCommand = durableOutput.command || {};
    require(
      durableCommand.type === "reallocate_workers",
      `Durable output command type=${durableCommand.type}, expected reallocate_workers`,
    );
    const durableWorkerIds = sortedUnique((durableCommand.payload || {}).worker_ids || []);

    // The crux: journal == Durable == applied command.
    require(
      setEqual(reallocatedIds, durableWorkerIds),
      `journal reallocated ${JSON.stringify(reallocatedIds)} != Durable output ${JSON.stringify(durableWorkerIds)}`,
    );
    require(
      setEqual(reallocatedIds, lastRespWorkerIds),
      `journal reallocated ${JSON.stringify(reallocatedIds)} != last_response command ${JSON.stringify(lastRespWorkerIds)}`,
    );

    // DOM: reallocated workers now appear in SUPPORT and left RESERVE.
    await waitFor(
      async () => {
        const support = await groupWorkerIds(page, "workers-support");
        return subset(reallocatedIds, support);
      },
      { deadline: DOM_DEADLINE, message: "reallocated workers never appeared in the SUPPORT group in the DOM" },
    );
    const domSupportAfter = sortedUnique(await groupWorkerIds(page, "workers-support"));
    const domReserveAfter = sortedUnique(await groupWorkerIds(page, "workers-reserve"));
    require(
      disjoint(reallocatedIds, domReserveAfter),
      `reallocated workers ${JSON.stringify(reallocatedIds)} still shown in RESERVE group`,
    );
    const newlyInSupport = domSupportAfter.filter((id) => !baselineSupport.includes(id));
    require(newlyInSupport.length > 0, "no worker newly appeared in the SUPPORT group in the DOM");
    require(
      subset(reallocatedIds, newlyInSupport),
      `reallocated ${JSON.stringify(reallocatedIds)} not all among newly-in-support ${JSON.stringify(newlyInSupport)}`,
    );
    require(
      subset(newlyInSupport, baselineReserve),
      `newly-in-support ${JSON.stringify(newlyInSupport)} are not all ex-reserve ${JSON.stringify(baselineReserve)}`,
    );

    // Strip text names the actual reallocated worker IDs, and its trace is
    // still the SAME across steps (step B).
    await waitFor(
      async () => {
        const text = await interventionText(page);
        return reallocatedIds.every((id) => text.includes(id));
      },
      { deadline: DOM_DEADLINE, message: "intervention strip never listed the reallocated worker IDs" },
    );
    const traceAtReallocation = await interventionTrace(page);
    require(
      traceAtReallocation === anchorTrace,
      `intervention strip trace changed across steps: ${traceAtIntervention} -> ${traceAtReallocation}`,
    );
    mark("reallocation_verified", {
      trace: anchorTrace,
      instance_id: instanceId,
      reallocated: reallocatedIds,
      durable_worker_ids: durableWorkerIds,
      dom_newly_in_support: newlyInSupport,
    });
    await shot("reallocated.png");

    // 7. A ticket.resolved after command.accepted; resolved card visible --
    const resolved = await waitFor(
      async () => {
        await journal.drain();
        const later = journal.byType("ticket.resolved").filter((e) => e.seq > commandAcceptedSeq);
        return later.length ? later[0] : null;
      },
      { deadline: RESOLVE_DEADLINE, message: `no ticket.resolved after command.accepted seq ${commandAcceptedSeq}` },
    );
    await waitFor(
      async () => (await page.locator('[data-testid="lane-resolved"] [data-testid^="ticket-"]').count()) > 0,
      { deadline: DOM_DEADLINE, message: "no resolved ticket card visible in the RESOLVED lane" },
    );
    mark("ticket_resolved_after_command", { seq: resolved.seq, ticket: resolved.actor_id });
    await shot("resolved.png");

    // 8. No aggregate WorldSignalsPanel survives (static, no extra process)-
    const panelCheck = assertNoWorldSignalsPanel();
    mark("world_signals_panel_absent");

    // No uncaught page exceptions — that would be a real UI bug.
    require(
      pageErrors.length === 0,
      `uncaught page errors on /world: ${JSON.stringify(pageErrors.slice(0, 5))}`,
    );

    // 9. Evidence + summary ----------------------------------------------
    write("events.json", journal.all());
    Object.assign(summary, {
      result: "PASS",
      ui_base: UI_BASE,
      api_base: API_BASE,
      func_base: FUNC_BASE,
      task_hub: TASK_HUB,
      trace_id: anchorTrace,
      baseline_seq: baselineSeq,
      baseline_reserve_ids: baselineReserve,
      baseline_support_count: baselineSupport.length,
      waiting_accumulation: {
        baseline_count: baselineWaiting.length,
        pressure_count: accumulation.current.length,
        new_ticket_sample: accumulation.fresh.slice(0, 8),
      },
      reallocated_worker_ids: reallocatedIds,
      durable: {
        instance_id: instanceId,
        runtime_status: durable.runtimeStatus,
        command_type: durableCommand.type,
        worker_ids: durableWorkerIds,
        reasoning: durableOutput.reasoning,
      },
      last_response_worker_ids: lastRespWorkerIds,
      dom_support_after: domSupportAfter,
      dom_newly_in_support: newlyInSupport,
      dom_reserve_after: domReserveAfter,
      intervention_trace_steps: [traceAtIntervention, traceAtReallocation],
      command_accepted_seq: commandAcceptedSeq,
      ticket_resolved_after_command: { seq: resolved.seq, ticket_id: resolved.actor_id },
      world_signals_panel: panelCheck,
      console_errors: consoleErrors,
      page_errors: pageErrors,
      events_captured: journal.all().length,
      screenshots: ["baseline.png", "pressure.png", "intervention.png", "reallocated.png", "resolved.png"],
      elapsed_seconds: +((Date.now() - startedAt) / 1000).toFixed(3),
      timeline,
      evidence_dir: OUT_DIR,
    });
    write("summary.json", summary);
  } catch (err) {
    summary.result = "FAIL";
    summary.reason = err instanceof Error ? err.message : String(err);
    summary.timeline = timeline;
    summary.console_errors = consoleErrors;
    summary.page_errors = pageErrors;
    try {
      await shot("failure.png");
    } catch {
      /* best effort */
    }
    write("summary.json", summary);
    // Save the video before we rethrow.
    try {
      const video = page.video();
      await context.close();
      if (video) await video.saveAs(path.join(OUT_DIR, "session.webm"));
    } catch {
      /* best effort */
    }
    await browser.close();
    throw err;
  }

  // Finalise the video (needs the context closed to flush).
  try {
    const video = page.video();
    await context.close();
    if (video) await video.saveAs(path.join(OUT_DIR, "session.webm"));
  } catch {
    /* best effort */
  }
  await browser.close();
  return summary;
}

run()
  .then((summary) => {
    console.log(JSON.stringify(summary, null, 2));
    process.exit(0);
  })
  .catch((err) => {
    console.error(JSON.stringify({ result: "FAIL", reason: err.message }, null, 2));
    process.exit(1);
  });
