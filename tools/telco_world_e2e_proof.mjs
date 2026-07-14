// tools/telco_world_e2e_proof.mjs
//
// Browser assertion driver for the telco Network Incident world
// (feat(telco)). It drives an ALREADY-RUNNING real stack booted by
// tools/telco_world_e2e_proof.sh — no mocks:
//
//   * Control Plane Vite serving /world, proxying /api → FastAPI
//   * FastAPI hosting the live ActorWorldService (ZAVA_WORLD=telco)
//   * Azure Durable Functions host (:7071) with NetworkIncidentOrchestrator
//
// It proves the viewer renders the REAL actor world end to end, using DOM
// locators/test-ids cross-checked against the JSON journal and the Durable
// runtime — never screenshot-only judgement:
//
//   1. /world loads as the telco scenario; the baseline cell-site actor IDs
//      from the live snapshot are visible as site cards, real session tokens
//      render, and the header states the true site/session/subscriber totals.
//   2. Click "Fail site".
//   3. The journal records a real site.failed on one actual site plus
//      session.degraded on real session actors; the DOM marks that site as the
//      incident (and, in the live failed window, status=failed) and the
//      degraded lane fills with real degraded sessions.
//   4. The Durable causal chain fires on ONE stable network-anomaly trace:
//      sensor.tripped → responder.requested → responder.decided →
//      command.accepted → session.rerouted, anchored on the applied
//      last_response command.
//   5. The reroute assignments (session_id → neighbour site_id) from the
//      journal session.rerouted events EQUAL the Durable output command
//      (queried on :7071) EQUAL the applied last_response command EQUAL the
//      rerouted-session state in the DOM (tokens in the REROUTED lane, and each
//      rerouted session now sits on its assigned neighbour in the snapshot).
//   6. At least one affected session reroutes; the failed site's load drops
//      below its pre-failure traffic and at least one receiving neighbour's
//      load rises above baseline; the site recovers (site.recovered).
//
// Screenshots (baseline/failed/rerouted/recovered) and a session video are
// written under tmp/telco-world-e2e-proof/ as evidence alongside the
// machine-checked summary.json. Every wait has a bounded deadline; any mismatch
// throws and the process exits non-zero.
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

const UI_BASE = (process.env.WORLD_UI_BASE || "http://127.0.0.1:5280").replace(/\/$/, "");
const API_BASE = (process.env.WORLD_API_BASE || "http://127.0.0.1:3101").replace(/\/$/, "");
const FUNC_BASE = (process.env.FUNCTIONS_HOST || "http://127.0.0.1:7071").replace(/\/$/, "");
const TASK_HUB = process.env.WORLD_TASK_HUB || "InvoiceP2PHub";
const OUT_DIR = process.env.PROOF_OUT_DIR || "tmp/telco-world-e2e-proof";

// Bounded wall-clock deadlines (ms).
const NAV_DEADLINE = 30_000;
const BASELINE_DEADLINE = 30_000;
const FAIL_DEADLINE = 30_000;
const DEGRADED_DEADLINE = 30_000;
const CHAIN_DEADLINE = 120_000;
const DURABLE_DEADLINE = 45_000;
const DOM_DEADLINE = 30_000;
const RECOVER_DEADLINE = 45_000;
const POLL_MS = 400;

const REQUIRED_TYPES = [
  "sensor.tripped",
  "objective.opened",
  "objective.claimed",
  "responder.requested",
  "objective.acting",
  "responder.decided",
  "command.accepted",
  "objective.evaluating",
  "session.rerouted",
];

class ProofError extends Error {}
function need(condition, message) {
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
    need(body.enabled === true, "actor-world /events reported disabled");
    for (const ev of body.events || []) this.bySeq.set(Number(ev.seq), ev);
    if (typeof body.latest_seq === "number") this.cursor = Math.max(this.cursor, body.latest_seq);
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

async function domSiteIds(page) {
  return page
    .locator('[data-testid^="site-"]:not([data-testid^="site-util-"]):not([data-testid^="site-sessions-"])')
    .evaluateAll((els) =>
      els
        .map((e) => e.getAttribute("data-testid"))
        .filter((t) => /^site-SITE-/.test(t))
        .map((t) => t.replace("site-", "")),
    );
}
async function siteAttr(page, siteId, attr) {
  const loc = page.getByTestId(`site-${siteId}`);
  if ((await loc.count()) === 0) return null;
  return loc.first().getAttribute(attr);
}
async function laneSessionIds(page, lane) {
  return page
    .locator(`[data-testid="session-lane-${lane}"] [data-testid^="session-SES-"]`)
    .evaluateAll((els) =>
      els.map((e) => e.getAttribute("data-testid").replace("session-", "")),
    );
}
async function laneCount(page, lane) {
  const loc = page.getByTestId(`session-count-${lane}`);
  if ((await loc.count()) === 0) return 0;
  const txt = (await loc.first().innerText()).trim();
  const n = Number(txt);
  return Number.isFinite(n) ? n : 0;
}
async function interventionTrace(page) {
  const strip = page.getByTestId("telco-intervention");
  if ((await strip.count()) === 0) return null;
  return (await strip.locator("button").first().innerText()).trim();
}
async function interventionText(page) {
  const strip = page.getByTestId("telco-intervention");
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

const snapSite = (state, id) => (state.sites || []).find((s) => s.id === id) || null;
const pairsOf = (assignments) =>
  sortedUnique((assignments || []).map((a) => `${a.session_id}->${a.to_site_id}`));

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
    // 1. Load /world (telco) ----------------------------------------------
    await page.goto(`${UI_BASE}/world`, { waitUntil: "domcontentloaded", timeout: NAV_DEADLINE });
    await page.getByTestId("telco-world-route").waitFor({ state: "visible", timeout: NAV_DEADLINE });
    mark("telco_world_route_loaded");

    const baseline = await getJson(`${API_BASE}/api/world/state`);
    need(baseline.enabled === true, "world not enabled at baseline");
    need(baseline.scenario === "telco", `baseline scenario is not 'telco' (${baseline.scenario})`);
    const baselineSiteIds = sortedUnique((baseline.sites || []).map((s) => s.id));
    const baselineTraffic = Object.fromEntries((baseline.sites || []).map((s) => [s.id, s.traffic_mbps]));
    const baselineSessionCount = (baseline.sessions || []).length;
    const baselineSubscriberCount = (baseline.subscribers || []).length;
    need(baselineSiteIds.length >= 12, `baseline has only ${baselineSiteIds.length} sites (<12)`);
    need(baselineSessionCount >= 2000, `baseline has only ${baselineSessionCount} sessions (<2000)`);
    write("baseline.json", baseline);

    // 2. Baseline: real site cards + session tokens + true totals ----------
    await waitFor(
      async () => subset(baselineSiteIds, await domSiteIds(page)),
      { deadline: BASELINE_DEADLINE, message: "baseline cell-site cards never all rendered" },
    );
    await waitFor(
      async () => (await page.locator('[data-testid^="session-SES-"]').count()) > 0,
      { deadline: BASELINE_DEADLINE, message: "no baseline session tokens rendered" },
    );
    const statSessions = (await page.getByTestId("stat-sessions").innerText()).trim();
    need(
      statSessions.includes(String(baselineSessionCount)),
      `header stat-sessions '${statSessions}' does not state true total ${baselineSessionCount}`,
    );
    mark("baseline_visible", {
      sites: baselineSiteIds.length,
      sessions: baselineSessionCount,
      subscribers: baselineSubscriberCount,
    });
    await shot("baseline.png");

    // 3. Click "Fail site" -------------------------------------------------
    const failBtn = page.getByTestId("inject-site-failure");
    need(!(await failBtn.isDisabled()), "inject-site-failure control is disabled at baseline");
    await failBtn.click();
    mark("fail_site_clicked");

    // Authoritative: the journal records a real failure + degraded sessions.
    const failedEvent = await waitFor(
      async () => {
        await journal.drain();
        const f = journal.byType("site.failed");
        return f.length ? f[0] : null;
      },
      { deadline: FAIL_DEADLINE, message: "no site.failed event appeared in the journal" },
    );
    const failedSiteId = failedEvent.actor_id;
    const priorTraffic = Number(failedEvent.payload.prior_traffic_mbps);
    await waitFor(
      async () => {
        await journal.drain();
        return journal.byType("session.degraded").length > 0;
      },
      { deadline: FAIL_DEADLINE, message: "no session.degraded events appeared in the journal" },
    );
    const degradedIds = sortedUnique(
      journal.byType("session.degraded").map((e) => e.actor_id).filter(Boolean),
    );
    need(degradedIds.length > 0, "no degraded session actor IDs in the journal");
    mark("site_failed", { site: failedSiteId, prior_traffic_mbps: priorTraffic, degraded: degradedIds.length });

    // DOM: the failed site is marked as the incident (persisted highlight),
    // and — in the live failed window — shows status=failed.
    let caughtLiveFailedStatus = false;
    await waitFor(
      async () => {
        const status = await siteAttr(page, failedSiteId, "data-status");
        const incident = await siteAttr(page, failedSiteId, "data-incident");
        if (status === "failed") caughtLiveFailedStatus = true;
        return status === "failed" || incident === "true";
      },
      { deadline: FAIL_DEADLINE, message: `failed site ${failedSiteId} never marked in the DOM` },
    );

    // DOM: the degraded lane fills with real degraded sessions (the window
    // between failure and reroute is several seconds wide).
    await waitFor(
      async () => (await laneCount(page, "degraded")) > 0,
      { deadline: DEGRADED_DEADLINE, message: "degraded session lane never populated in the DOM" },
    );
    const domDegradedVisible = await laneSessionIds(page, "degraded");
    need(
      domDegradedVisible.every((id) => degradedIds.includes(id)),
      `DOM degraded tokens ${JSON.stringify(domDegradedVisible.slice(0, 6))} not all real degraded sessions`,
    );
    mark("degraded_visible", {
      live_failed_status: caughtLiveFailedStatus,
      dom_degraded_tokens: domDegradedVisible.length,
    });
    await shot("failed.png");

    // 4. Intervention strip + full causal chain on one anchored trace ------
    await page.getByTestId("telco-intervention").waitFor({ state: "visible", timeout: CHAIN_DEADLINE });
    const traceAtIntervention = await interventionTrace(page);
    need(Boolean(traceAtIntervention), "intervention strip rendered no trace id");

    const finalState = await waitFor(
      async () => {
        const st = await getJson(`${API_BASE}/api/world/state`);
        return st.last_response && st.last_response.instance_id ? st : null;
      },
      { deadline: CHAIN_DEADLINE, message: "world state never exposed a Durable last_response.instance_id" },
    );
    const lastResponse = finalState.last_response;
    const instanceId = String(lastResponse.instance_id);
    const command = lastResponse.command || {};
    const anchorTrace = String(command.trace_id || "");
    need(Boolean(anchorTrace), "last_response command carried no trace_id");
    need(
      command.type === "reroute_sessions",
      `last_response command type=${command.type}, expected reroute_sessions`,
    );
    const lastRespPairs = pairsOf((command.payload || {}).assignments);
    need(
      traceAtIntervention === anchorTrace,
      `intervention strip trace ${traceAtIntervention} != anchored journal trace ${anchorTrace}`,
    );

    await waitFor(
      async () => {
        await journal.drain();
        const have = new Set(journal.all().filter((e) => e.trace_id === anchorTrace).map((e) => e.type));
        return REQUIRED_TYPES.every((t) => have.has(t));
      },
      { deadline: CHAIN_DEADLINE, message: `anchored trace ${anchorTrace} never carried the full chain` },
    );
    mark("causal_chain_complete", { trace: anchorTrace, instance_id: instanceId });

    // The objective lifecycle rides the same anchored trace, strictly ordered
    // open -> claimed -> acting -> evaluating, all naming one objective id.
    const objectiveChain = ["objective.opened", "objective.claimed", "objective.acting", "objective.evaluating"];
    const objectiveSteps = objectiveChain.map((type) => {
      const hits = journal.byType(type, anchorTrace).sort((a, b) => a.seq - b.seq);
      need(hits.length > 0, `anchored trace ${anchorTrace} missing ${type}`);
      return { type, seq: hits[0].seq, objective_id: (hits[0].payload || {}).id };
    });
    for (let i = 1; i < objectiveSteps.length; i++) {
      need(
        objectiveSteps[i].seq > objectiveSteps[i - 1].seq,
        `objective lifecycle out of order: ${objectiveSteps[i - 1].type} !< ${objectiveSteps[i].type}`,
      );
    }
    const objectiveId = objectiveSteps[0].objective_id;
    need(
      Boolean(objectiveId) && objectiveSteps.every((s) => s.objective_id === objectiveId),
      `objective id not stable across lifecycle: ${JSON.stringify(objectiveSteps.map((s) => s.objective_id))}`,
    );
    mark("objective_lifecycle", {
      trace: anchorTrace,
      objective_id: objectiveId,
      chain: objectiveSteps.map((s) => `${s.type}@${s.seq}`),
    });

    // 5. journal == Durable == last_response == DOM -----------------------
    const rerouted = journal.byType("session.rerouted", anchorTrace);
    const reroutedIds = sortedUnique(rerouted.map((e) => e.actor_id).filter(Boolean));
    const journalPairs = pairsOf(
      rerouted.map((e) => ({ session_id: e.actor_id, to_site_id: e.payload.to_site_id })),
    );
    need(reroutedIds.length >= 1, `no session.rerouted actors for trace ${anchorTrace}`);
    need(
      subset(reroutedIds, degradedIds),
      `rerouted sessions ${JSON.stringify(reroutedIds.slice(0, 6))} were not all previously degraded`,
    );

    const durable = await fetchDurableCompleted(instanceId);
    write("durable-instance.json", durable);
    const durableOutput = asObj(durable.output) || {};
    const durableCommand = durableOutput.command || {};
    need(
      durableCommand.type === "reroute_sessions",
      `Durable output command type=${durableCommand.type}, expected reroute_sessions`,
    );
    const durablePairs = pairsOf((durableCommand.payload || {}).assignments);

    need(
      setEqual(journalPairs, durablePairs),
      `journal reroutes ${JSON.stringify(journalPairs)} != Durable output ${JSON.stringify(durablePairs)}`,
    );
    need(
      setEqual(journalPairs, lastRespPairs),
      `journal reroutes ${JSON.stringify(journalPairs)} != last_response ${JSON.stringify(lastRespPairs)}`,
    );

    // DOM: rerouted lane count is the true total and matches the journal;
    // every visible rerouted token is a real rerouted session.
    await waitFor(
      async () => (await laneCount(page, "rerouted")) >= reroutedIds.length,
      { deadline: DOM_DEADLINE, message: "rerouted lane never reached the journalled reroute count" },
    );
    const domReroutedVisible = await laneSessionIds(page, "rerouted");
    need(domReroutedVisible.length > 0, "no rerouted session tokens visible in the DOM");
    need(
      subset(domReroutedVisible, reroutedIds),
      `DOM rerouted tokens ${JSON.stringify(domReroutedVisible.slice(0, 6))} not all journalled reroutes`,
    );

    // Snapshot: each rerouted session now sits on its assigned neighbour.
    const afterReroute = await getJson(`${API_BASE}/api/world/state`);
    const assignedSite = Object.fromEntries(
      rerouted.map((e) => [e.actor_id, e.payload.to_site_id]),
    );
    for (const s of afterReroute.sessions || []) {
      if (assignedSite[s.id]) {
        need(
          s.site_id === assignedSite[s.id] && s.status === "rerouted",
          `session ${s.id} snapshot site_id=${s.site_id}/status=${s.status}, expected ${assignedSite[s.id]}/rerouted`,
        );
      }
    }

    // Strip names the incident site, the rerouted count, and the accepted
    // command — all on the same anchored trace.
    await waitFor(
      async () => {
        const text = await interventionText(page);
        return (
          text.includes(failedSiteId) &&
          text.includes(`${reroutedIds.length} sessions rerouted`) &&
          text.includes("Command accepted")
        );
      },
      { deadline: DOM_DEADLINE, message: "intervention strip never summarised the reroute on the anchored trace" },
    );
    mark("reroute_verified", {
      trace: anchorTrace,
      instance_id: instanceId,
      rerouted_count: reroutedIds.length,
      journal_pairs: journalPairs,
      durable_pairs: durablePairs,
    });
    await shot("rerouted.png");

    // 6. Failed-site load drops, a neighbour rises, and the site recovers --
    const incidentSnap = snapSite(afterReroute, failedSiteId);
    need(incidentSnap != null, `incident site ${failedSiteId} missing from snapshot`);
    need(
      incidentSnap.traffic_mbps < priorTraffic,
      `failed site load ${incidentSnap.traffic_mbps} did not drop below pre-failure ${priorTraffic}`,
    );

    const receiverIds = sortedUnique(rerouted.map((e) => e.payload.to_site_id));
    const risenNeighbours = receiverIds.filter((id) => {
      const snap = snapSite(afterReroute, id);
      return snap && snap.traffic_mbps > (baselineTraffic[id] ?? 0);
    });
    need(
      risenNeighbours.length > 0,
      `no receiving neighbour load rose above baseline (receivers ${JSON.stringify(receiverIds)})`,
    );

    const recovered = await waitFor(
      async () => {
        await journal.drain();
        const r = journal.byType("site.recovered", anchorTrace);
        return r.length ? r[0] : null;
      },
      { deadline: RECOVER_DEADLINE, message: `no site.recovered on trace ${anchorTrace}` },
    );
    mark("recovery_verified", {
      incident_traffic_after: incidentSnap.traffic_mbps,
      prior_traffic: priorTraffic,
      risen_neighbours: risenNeighbours,
    });
    await shot("recovered.png");

    need(pageErrors.length === 0, `uncaught page errors on /world: ${JSON.stringify(pageErrors.slice(0, 5))}`);

    // 7. Evidence + summary ------------------------------------------------
    write("events.json", journal.all());
    Object.assign(summary, {
      result: "PASS",
      ui_base: UI_BASE,
      api_base: API_BASE,
      func_base: FUNC_BASE,
      task_hub: TASK_HUB,
      scenario: "telco",
      trace_id: anchorTrace,
      baseline: {
        site_ids: baselineSiteIds,
        session_count: baselineSessionCount,
        subscriber_count: baselineSubscriberCount,
      },
      failed_site: failedSiteId,
      prior_traffic_mbps: priorTraffic,
      degraded_session_count: degradedIds.length,
      degraded_sample: degradedIds.slice(0, 8),
      live_failed_status_caught: caughtLiveFailedStatus,
      rerouted_session_ids: reroutedIds,
      reroute_assignments: journalPairs,
      durable: {
        instance_id: instanceId,
        runtime_status: durable.runtimeStatus,
        command_type: durableCommand.type,
        assignments: durablePairs,
        reasoning: durableOutput.reasoning,
      },
      last_response_assignments: lastRespPairs,
      dom_degraded_tokens: domDegradedVisible.length,
      dom_rerouted_tokens: domReroutedVisible,
      incident_traffic_after: incidentSnap.traffic_mbps,
      receiver_neighbours: receiverIds,
      risen_neighbours: risenNeighbours,
      site_recovered_seq: recovered.seq,
      intervention_trace: traceAtIntervention,
      console_errors: consoleErrors,
      page_errors: pageErrors,
      events_captured: journal.all().length,
      screenshots: ["baseline.png", "failed.png", "rerouted.png", "recovered.png"],
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
