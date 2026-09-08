import { chromium } from "playwright";
import {
  mkdir,
  readdir,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

// ── Airline proof contract ──────────────────────────────────────────
export const WORKFLOW_CONTRACTS = [
  {
    scenario: "synthetic-hub-cascade",
    workflow: "integrated-hub-disruption-recovery",
    orchestrator: "AirlineIntegratedHubRecoveryOrchestrator",
    phases: [
      "Detect Hub Disruption",
      "Assess Network Impact",
      "Synthesize Recovery Options",
      "Approve Recovery Plan",
      "Commit Recovery Actions",
      "Verify Recovery Outcome",
    ],
    hitl_persona: "duty_operations_manager",
    hitl_event: "duty_operations_manager_decision",
    command: "airline.commit_recovery_plan",
    success_event: "airline.recovery.applied",
    prefix: "AIRHUB",
  },
  {
    scenario: "synthetic-aog-defect",
    workflow: "aog-engineering-recovery",
    orchestrator: "AirlineAogEngineeringRecoveryOrchestrator",
    phases: [
      "Detect AOG Event",
      "Check Airworthiness Constraints",
      "Synthesize Engineering Recovery Options",
      "Approve Engineering Recovery",
      "Commit Engineering and Operational Actions",
      "Verify Recovery State",
    ],
    hitl_persona: "engineering_duty_manager",
    hitl_event: "engineering_duty_manager_decision",
    command: "airline.commit_aog_recovery",
    success_event: "airline.aog_recovery.applied",
    prefix: "AOGA",
  },
  {
    scenario: "synthetic-schedule-restriction",
    workflow: "preemptive-schedule-resilience",
    orchestrator: "AirlineScheduleResilienceOrchestrator",
    phases: [
      "Detect Schedule Risk Signal",
      "Assess Network Ripple Effects",
      "Synthesize Resilience Options",
      "Approve Schedule Adjustment",
      "Commit Schedule Adjustment",
      "Verify Network Stability",
    ],
    hitl_persona: "network_operations_director",
    hitl_event: "network_operations_director_decision",
    command: "airline.commit_schedule_adjustment",
    success_event: "airline.schedule_adjustment.applied",
    prefix: "AIRSCHED",
  },
];

export const SURFACES = [
  "world",
  "workflow-api",
  "workflow-drawer",
  "memory",
  "knowledge",
  "ag-ui",
  "graph-projection",
  "constellation",
];

if (process.argv[2] === "--print-contract") {
  console.log(JSON.stringify({ contracts: WORKFLOW_CONTRACTS, surfaces: SURFACES }));
  process.exit(0);
}

// ── Configuration ───────────────────────────────────────────────────
const API = (process.env.WORLD_API_BASE || "http://127.0.0.1:13201").replace(/\/$/, "");
const CONTROL_PLANE = (
  process.env.CONTROL_PLANE_BASE || "http://127.0.0.1:15373"
).replace(/\/$/, "");
const BLUEPRINT = (
  process.env.BLUEPRINT_BASE || "http://127.0.0.1:15375"
).replace(/\/$/, "");
const FUNCTIONS = (
  process.env.FUNCTIONS_HOST || "http://127.0.0.1:17271"
).replace(/\/$/, "");
const OUT_DIR = process.env.PROOF_OUT_DIR || "tmp/airline-zava-e2e-proof";
const SCREENSHOTS = path.join(OUT_DIR, "screenshots");
const VIDEO = path.join(OUT_DIR, "video");
const RECORDINGS = path.join(OUT_DIR, "recordings");
const POLL_MS = 500;
const WORKFLOW_DEADLINE_MS = 12 * 60 * 1000;
const UI_DEADLINE_MS = 45_000;
const HITL_RESOLVE_DEADLINE_MS = 15_000;
const CLICK_TO_VISIBLE_MS = 1_000;

class ProofError extends Error {}

function need(condition, message) {
  if (!condition) throw new ProofError(message);
}

async function ensureEvidenceDirs() {
  await Promise.all([
    mkdir(OUT_DIR, { recursive: true }),
    mkdir(SCREENSHOTS, { recursive: true }),
    mkdir(VIDEO, { recursive: true }),
    mkdir(RECORDINGS, { recursive: true }),
  ]);
}

async function writeJson(name, value) {
  await writeFile(
    path.join(OUT_DIR, name),
    JSON.stringify(value, null, 2),
    "utf8",
  );
}

async function requestJson(method, route, data) {
  const response = await fetch(`${API}${route}`, {
    method,
    headers: data === undefined ? undefined : { "content-type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (!response.ok) {
    throw new ProofError(`${method} ${route}: ${response.status} ${await response.text()}`);
  }
  return response.json();
}

const getJson = (route) => requestJson("GET", route);
const postJson = (route, data) => requestJson("POST", route, data);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function readReplayMeta() {
  return getJson("/api/replay/meta");
}

async function sweepPersonas() {
  const response = await fetch(`${API}/api/personas/sweep`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    throw new ProofError(`POST /api/personas/sweep: ${response.status} ${await response.text()}`);
  }
  return response.json();
}

async function waitFor(check, message, deadline = UI_DEADLINE_MS) {
  const end = Date.now() + deadline;
  let lastError;
  while (Date.now() < end) {
    try {
      const value = await check();
      if (value) return value;
    } catch (error) {
      if (error instanceof ProofError) throw error;
      lastError = error;
    }
    await sleep(POLL_MS);
  }
  const suffix = lastError ? `; last error: ${lastError.message}` : "";
  throw new ProofError(`${message}${suffix}`);
}

function workflowFailure(workflow) {
  const metadata = workflow.metadata || {};
  const payload = workflow.payload || {};
  return (
    metadata.failure_reason
    || payload.reason
    || payload.error
    || `workflow ${workflow.id} failed`
  );
}

async function listWorkflows() {
  return getJson("/api/workflows");
}

async function fetchDurable(instanceId) {
  const response = await fetch(
    `${FUNCTIONS}/runtime/webhooks/durabletask/instances/${instanceId}`,
  );
  if (!response.ok) {
    throw new ProofError(`Durable ${instanceId}: HTTP ${response.status}`);
  }
  const body = await response.json();
  need(
    body.runtimeStatus === "Completed",
    `Durable ${instanceId} ended ${body.runtimeStatus}: ${body.output}`,
  );
  return body;
}

function installBrowserTracking(page, name, evidence) {
  page.on("pageerror", (error) => {
    evidence.browserErrors.push(`${name}: ${error.message}`);
  });
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("favicon.ico")) {
      evidence.browserErrors.push(`${name}: ${message.text()}`);
    }
  });
  page.on("response", (response) => {
    if (response.status() >= 400 && !response.url().includes("favicon.ico")) {
      evidence.browserErrors.push(
        `${name}: HTTP ${response.status()} ${response.url()}`,
      );
    }
  });
  page.on("requestfailed", (request) => {
    const error = request.failure()?.errorText || "request failed";
    if (error.includes("ERR_ABORTED")) {
      evidence.expectedAborts.push(`${name}: ${request.url()}`);
    } else {
      evidence.browserErrors.push(`${name}: ${error} ${request.url()}`);
    }
  });
}

async function gotoUi(page, url) {
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      await page.goto(url, {
        waitUntil: "domcontentloaded",
        timeout: UI_DEADLINE_MS,
      });
      return;
    } catch (error) {
      if (error.name !== "TimeoutError" || attempt === 2) throw error;
      await sleep(1_000);
    }
  }
}

async function openConstellation(context, evidence) {
  const page = await context.newPage();
  installBrowserTracking(page, "constellation", evidence);
  await gotoUi(page, `${BLUEPRINT}/?view=constellation`);
  await page.locator("canvas").first().waitFor({ timeout: UI_DEADLINE_MS });
  await page.evaluate(() => {
    window.__airlineProofEvents = [];
    window.__airlineProofSource = new EventSource("/api/blueprint/stream");
    window.__airlineProofSource.addEventListener("event", (event) => {
      try {
        window.__airlineProofEvents.push(JSON.parse(event.data));
      } catch {
        // Ignore keep-alives and malformed messages.
      }
    });
  });
  return page;
}

function screenshotPath(contract, surface) {
  return path.join(SCREENSHOTS, `${contract.workflow}-${surface}.png`);
}

function createdAtValue(workflow) {
  return Date.parse(workflow.createdAt || workflow.created_at || 0) || 0;
}

function ensureSurfaceBucket(evidence, surface) {
  if (!evidence.surfaces[surface]) evidence.surfaces[surface] = {};
  return evidence.surfaces[surface];
}

// Bounded backend restart / cursor-rewind recovery: if the backend is restarted
// and /api/world/events reports latest_seq below the client cursor, replay from
// after=0 without a manual refresh.
async function drainWorldJournal(cursor) {
  let route = `/api/world/events?after=${cursor}`;
  let body = await getJson(route);
  need(body.enabled !== false, "actor world disabled while reading journal");
  let rewound = false;
  if (typeof body.latest_seq === "number" && body.latest_seq < cursor) {
    route = "/api/world/events?after=0";
    body = await getJson(route);
    rewound = true;
  }
  const maxSeen = Math.max(
    typeof body.latest_seq === "number" ? body.latest_seq : 0,
    ...((body.events || []).map((event) => Number(event.seq) || 0)),
  );
  return {
    route,
    body,
    cursor: maxSeen,
    rewound,
  };
}

async function requireWorkflowRecording(workflowType) {
  const files = (await readdir(RECORDINGS)).filter((name) => name.startsWith(`${workflowType}-`) && name.endsWith(".jsonl"));
  for (const name of files) {
    const details = await stat(path.join(RECORDINGS, name));
    if (details.size > 0) return name;
  }
  throw new ProofError(`recorder produced no non-empty ${workflowType}-*.jsonl replay`);
}

async function assertLiveSurfaces(context, evidence, contract, workflow, graph, detail, constellation) {
  const page = await context.newPage();
  installBrowserTracking(page, `${contract.workflow}-control-plane`, evidence);

  const worldPayload = await getJson("/api/world/events?after=0");
  const worldEvents = Array.isArray(worldPayload.events) ? worldPayload.events : [];
  const worldWfEvents = worldEvents.filter(
    (event) =>
      event.workflow_id === workflow.id ||
      event.workflowId === workflow.id ||
      event.payload?.workflow_id === workflow.id ||
      event.payload?.workflowId === workflow.id,
  );
  const terminalWorldEvent = worldWfEvents.find(
    (event) => event.type === contract.success_event || event.status === "completed",
  );
  need(worldWfEvents.length > 0, `World event log has no events for workflow ${workflow.id}`);
  need(
    terminalWorldEvent,
    `World event log has no terminal success event for workflow ${workflow.id}`,
  );
  ensureSurfaceBucket(evidence, "world")[workflow.id] = {
    workflowId: workflow.id,
    eventCount: worldWfEvents.length,
    terminalEvent: terminalWorldEvent?.type || worldWfEvents.at(-1)?.type,
  };
  await gotoUi(page, `${CONTROL_PLANE}/world`);
  await page.getByText("Synthetic Airline Hub Operations", { exact: false }).first().waitFor({
    timeout: UI_DEADLINE_MS,
  });
  await page.screenshot({ path: screenshotPath(contract, "world"), fullPage: true });

  // evidence.surfaces["workflow-api"] — per-workflow keyed bucket
  ensureSurfaceBucket(evidence, "workflow-api")[workflow.id] = {
    workflowId: workflow.id,
    type: detail.workflow.type,
    status: detail.workflow.status,
    phase: detail.workflow.currentPhase,
  };

  const drawerStart = Date.now();
  await page.goto(`${CONTROL_PLANE}/workflows/${workflow.id}`);
  await page.getByText(workflow.id, { exact: false }).first().waitFor({ timeout: CLICK_TO_VISIBLE_MS });
  const drawerMs = Date.now() - drawerStart;
  need(drawerMs <= 1_000, `workflow-drawer click-to-visible ${drawerMs}ms > 1000ms`);
  ensureSurfaceBucket(evidence, "workflow-drawer")[workflow.id] = {
    workflowId: workflow.id,
    clickToVisibleMs: drawerMs,
  };
  await page.screenshot({ path: screenshotPath(contract, "workflow-drawer"), fullPage: true });

  await page.goto(`${CONTROL_PLANE}/memory`);
  await page.getByRole("heading", { name: "Memory" }).waitFor();
  await page.locator("select").selectOption(contract.workflow);
  await page.getByText(workflow.id, { exact: false }).waitFor();
  ensureSurfaceBucket(evidence, "memory")[workflow.id] = { workflowId: workflow.id };
  await page.screenshot({ path: screenshotPath(contract, "memory"), fullPage: true });

  await page.goto(`${CONTROL_PLANE}/knowledge`);
  await page.getByRole("heading", { name: "Knowledge" }).waitFor();
  const summary = page.getByText(/[1-9]\d* nodes · [1-9]\d* edges/);
  await summary.waitFor({ timeout: UI_DEADLINE_MS });
  const graphIds = new Set(Object.keys(graph.workflowNodes || {}));
  need(graphIds.has(workflow.id), `Knowledge graph missing ${workflow.id}`);
  ensureSurfaceBucket(evidence, "knowledge")[workflow.id] = {
    workflowId: workflow.id,
    summary: await summary.innerText(),
    hasWorkflowNode: true,
  };
  await page.screenshot({ path: screenshotPath(contract, "knowledge"), fullPage: true });

  const projection = await getJson(`/api/entities/_graph?limit=2000`);
  const workflowNode = projection.nodes.find((node) => node.id === workflow.id);
  need(workflowNode, `Graph projection missing Workflow node ${workflow.id}`);
  const phaseEdges = projection.edges.filter(
    (edge) => edge.source === workflow.id || edge.target === workflow.id,
  );
  // evidence.surfaces["graph-projection"] — per-workflow keyed bucket
  ensureSurfaceBucket(evidence, "graph-projection")[workflow.id] = {
    workflowId: workflow.id,
    nodeLabel: workflowNode._label || workflowNode.label,
    connectedEdges: phaseEdges.length,
    totalNodes: projection.nodes.length,
    totalEdges: projection.edges.length,
  };

  const run = await context.newPage();
  installBrowserTracking(run, `${contract.workflow}-ag-ui`, evidence);
  await run.goto(`${BLUEPRINT}/?view=run&run_id=${workflow.id}`);
  await run.getByTestId("run-panel").waitFor();
  await run.getByText(`Workflow run: ${workflow.id}`, { exact: true }).waitFor();
  await run.getByText("finished", { exact: true }).waitFor();
  ensureSurfaceBucket(evidence, "ag-ui")[workflow.id] = { workflowId: workflow.id, status: "finished" };
  await run.screenshot({ path: screenshotPath(contract, "ag-ui"), fullPage: true });

  await waitFor(
    async () => {
      const events = await constellation.evaluate(() => window.__airlineProofEvents || []);
      return events.some((event) => event.workflow_id === workflow.id || event.workflowId === workflow.id)
        ? events
        : null;
    },
    `Constellation stream did not observe workflow ${workflow.id}`,
    60_000,
  );
  const streamEvents = await constellation.evaluate(() => window.__airlineProofEvents || []);
  ensureSurfaceBucket(evidence, "constellation")[workflow.id] = streamEvents
    .filter((event) => event.workflow_id === workflow.id || event.workflowId === workflow.id)
    .map((event) => event.type);
  await constellation.screenshot({ path: screenshotPath(contract, "constellation"), fullPage: true });
  await run.close();
  await page.close();
}

async function runLive() {
  await ensureEvidenceDirs();
  const replayWorkflowDetails = [];
  const evidence = {
    result: "PENDING",
    contracts: WORKFLOW_CONTRACTS,
    surfaces: {},
    workflowApi: {},
    durable: {},
    recorder: {},
    approvals: [],
    browserErrors: [],
    expectedAborts: [],
    droppedEvents: [],
    sourceMode: "live",
    ids: {},
    cursorRecovery: [],
  };
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    recordVideo: { dir: VIDEO, size: { width: 1600, height: 1000 } },
  });
  let constellation;
  let recorderStarted = false;
  try {
    constellation = await openConstellation(context, evidence);
    await postJson("/api/blueprint/_recorder/start");
    recorderStarted = true;

    let journalCursor = 0;
    const initial = await listWorkflows();
    const knownIds = new Set(initial.map((workflow) => workflow.id));
    const baselineJournal = await drainWorldJournal(journalCursor);
    journalCursor = baselineJournal.cursor;
    evidence.cursorRecovery.push({ phase: "baseline", cursor: journalCursor, rewound: baselineJournal.rewound });

    for (const contract of WORKFLOW_CONTRACTS) {
      const scenario = await postJson(`/api/world/scenarios/${contract.scenario}`);
      need(scenario.ok, `${contract.scenario} scenario was rejected`);

      const workflow = await waitFor(
        async () => {
          const workflows = await listWorkflows();
          const candidate = workflows
            .filter(
              (item) => item.type === contract.workflow
                && item.id?.startsWith(contract.prefix)
                && !knownIds.has(item.id),
            )
            .sort((left, right) => createdAtValue(right) - createdAtValue(left))[0];
          if (!candidate) return null;
          if (candidate.status === "failed") throw new ProofError(workflowFailure(candidate));
          return candidate;
        },
        `${contract.workflow} workflow did not appear`,
        WORKFLOW_DEADLINE_MS,
      );
      knownIds.add(workflow.id);
      evidence.ids[contract.workflow] = { workflowId: workflow.id, scenario: contract.scenario };

      const hitlEvidence = await waitFor(
        async () => {
          const workflows = await listWorkflows();
          const item = workflows.find((candidate) => candidate.id === workflow.id);
          if (!item) return null;
          if (item.status === "failed") throw new ProofError(workflowFailure(item));
          const directContext = item.payload?.hitl_context;
          const terminalContext = item.payload?.evidence?.hitl_context;
          if (item.status === "awaiting_hitl" && directContext) {
            return { workflow: item, hitlContext: directContext, observedAwaiting: true };
          }
          if (item.status === "completed" && terminalContext) {
            return { workflow: item, hitlContext: terminalContext, observedAwaiting: false };
          }
          return null;
        },
        `workflow ${workflow.id} did not persist HITL context`,
        WORKFLOW_DEADLINE_MS,
      );
      need(
        hitlEvidence.hitlContext,
        `workflow ${workflow.id} is missing persisted hitl_context`,
      );

      if (hitlEvidence.observedAwaiting) {
        const sweepResult = await sweepPersonas();
        evidence.approvals.push({
          workflowType: contract.workflow,
          persona: contract.hitl_persona,
          event: contract.hitl_event,
          method: "persona_sweep",
          result: sweepResult,
        });
      } else {
        evidence.approvals.push({
          workflowType: contract.workflow,
          persona: contract.hitl_persona,
          event: contract.hitl_event,
          method: "event_auto_close",
          result: { completedBeforePolling: true },
        });
      }

      const completedWorkflow = await waitFor(
        async () => {
          const events = await constellation.evaluate(() => window.__airlineProofEvents || []);
          const wfEvents = events.filter(
            (event) => event.workflow_id === workflow.id || event.workflowId === workflow.id,
          );
          const hasPersonaDecided = wfEvents.some((event) => event.type === "persona.decided");
          const hasDurableResumed = wfEvents.some((event) => event.type === "durable.resumed");
          if (!hasPersonaDecided || !hasDurableResumed) return null;

          const workflows = await listWorkflows();
          const item = workflows.find((candidate) => candidate.id === workflow.id);
          if (!item) return null;
          if (item.status === "failed") throw new ProofError(workflowFailure(item));
          return item.status === "completed" ? item : null;
        },
        `workflow ${workflow.id} did not reach terminal state with persona.decided + durable.resumed within deadline`,
        HITL_RESOLVE_DEADLINE_MS,
      );
      need(completedWorkflow.status === "completed", `${workflow.id} did not complete`);

      const lifecycleEvents = (await constellation.evaluate(() => window.__airlineProofEvents || []))
        .filter((event) => event.workflow_id === workflow.id || event.workflowId === workflow.id);
      const personaDecided = lifecycleEvents.find((event) => event.type === "persona.decided");
      const durableResumed = lifecycleEvents.find((event) => event.type === "durable.resumed");
      need(personaDecided, `persona.decided event not observed for target workflow ${workflow.id}`);
      need(durableResumed, `durable.resumed event not observed for target workflow ${workflow.id}`);

      const detail = await getJson(`/api/workflows/${encodeURIComponent(workflow.id)}`);
      replayWorkflowDetails.push(detail);
      evidence.workflowApi[workflow.id] = {
        workflowType: contract.workflow,
        type: detail.workflow.type,
        status: detail.workflow.status,
        phase: detail.workflow.currentPhase,
        phases: detail.phases.map((phase) => phase.name),
      };
      need(detail.workflow.type === contract.workflow, `expected workflow type ${contract.workflow}, got ${detail.workflow.type}`);
      need(detail.phases.length === 6, `expected 6 phases, got ${detail.phases.length}`);
      for (let index = 0; index < contract.phases.length; index += 1) {
        need(
          detail.phases[index].name === contract.phases[index],
          `phase ${index} expected "${contract.phases[index]}", got "${detail.phases[index].name}"`,
        );
      }

      const instanceId = detail.workflow.orchestrationInstanceId;
      need(instanceId, `${workflow.id} has no Durable instance ID`);
      evidence.durable[workflow.id] = await fetchDurable(instanceId);

      const worldState = await getJson("/api/world/state");
      const worldJournal = await getJson("/api/world/events?after=0");
      const graph = await getJson("/api/entities/_graph?limit=2000");
      need(graph.nodes.length > 0 && graph.edges.length > 0, "Knowledge graph has no connected topology");
      graph.workflowNodes = {};
      const node = await getJson(`/api/entities/${encodeURIComponent(workflow.id)}`);
      need(node.id === workflow.id && node._label === "Workflow", `entity graph did not persist Workflow ${workflow.id}`);
      graph.workflowNodes[workflow.id] = node;

      await assertLiveSurfaces(context, evidence, contract, workflow, graph, detail, constellation);

      const journalDelta = await drainWorldJournal(journalCursor);
      journalCursor = journalDelta.cursor;
      evidence.cursorRecovery.push({
        workflowType: contract.workflow,
        cursor: journalCursor,
        rewound: journalDelta.rewound,
        latest_seq: journalDelta.body.latest_seq,
        route: journalDelta.route,
      });
      await writeJson("world-state.json", worldState);
      await writeJson("world-journal.json", worldJournal);
    }

    evidence.recorder.stop = await postJson("/api/blueprint/_recorder/stop");
    recorderStarted = false;
    evidence.recorder.files = (await readdir(RECORDINGS)).sort();
    evidence.recordings = {};
    for (const contract of WORKFLOW_CONTRACTS) {
      evidence.recordings[contract.workflow] = await requireWorkflowRecording(contract.workflow);
    }

    const replayMeta = await readReplayMeta();
    evidence.sourceMode = replayMeta.mode || evidence.sourceMode;
    await writeJson("durable-instances.json", evidence.durable);
    await writeJson("workflow-details.json", { sourceMode: evidence.sourceMode, workflows: evidence.workflowApi });
    await writeJson("workflow-replay-details.json", {
      schemaVersion: 1,
      vertical: "airline",
      workflows: replayWorkflowDetails,
    });
    need(evidence.browserErrors.length === 0, `browser errors:\n${evidence.browserErrors.join("\n")}`);
    evidence.result = "PASS";
    await writeJson("summary.json", evidence);
    console.log(JSON.stringify(evidence, null, 2));
  } catch (error) {
    evidence.result = "FAIL";
    evidence.error = error.stack || error.message || String(error);
    await writeJson("summary.json", evidence);
    throw error;
  } finally {
    if (recorderStarted) {
      try {
        evidence.recorder.stop = await postJson("/api/blueprint/_recorder/stop");
      } catch {
        // Preserve the original proof failure.
      }
    }
    if (constellation) {
      await constellation.evaluate(() => window.__airlineProofSource?.close()).catch(() => {});
    }
    await context.close();
    await browser.close();
  }
}

async function runReplay() {
  await ensureEvidenceDirs();
  const evidence = {
    result: "PENDING",
    workflowTypes: [],
    browserErrors: [],
    expectedAborts: [],
    functionsHostReachable: null,
    worldEnabled: null,
    sourceMode: null,
  };
  for (const contract of WORKFLOW_CONTRACTS) {
    await requireWorkflowRecording(contract.workflow);
  }
  try {
    const controller = new AbortController();
    setTimeout(() => controller.abort(), 1_000);
    await fetch(`${FUNCTIONS}/admin/host/status`, { signal: controller.signal });
    evidence.functionsHostReachable = true;
  } catch {
    evidence.functionsHostReachable = false;
  }
  need(!evidence.functionsHostReachable, "Functions host is reachable during replay proof");

  const world = await getJson("/api/world/state");
  evidence.worldEnabled = world.enabled;
  need(world.enabled === false, "actor world is enabled during replay proof");

  const replayMeta = await readReplayMeta();
  evidence.sourceMode = replayMeta.mode;
  need(evidence.sourceMode === "replay", `Replay proof expected sourceMode replay, got ${evidence.sourceMode}`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const page = await context.newPage();
  installBrowserTracking(page, "replay", evidence);
  try {
    await gotoUi(page, `${BLUEPRINT}/?view=constellation`);
    await page.locator("canvas").first().waitFor({ timeout: UI_DEADLINE_MS });
    await page.evaluate(() => {
      window.__airlineReplayEvents = [];
      window.__airlineReplaySource = new EventSource("/api/blueprint/stream");
      window.__airlineReplaySource.addEventListener("event", (event) => {
        try {
          window.__airlineReplayEvents.push(JSON.parse(event.data));
        } catch {
          // Ignore keep-alives.
        }
      });
    });
    await postJson("/api/blueprint/_demo_stream/start");
    const types = await waitFor(
      async () => {
        const events = await page.evaluate(() => window.__airlineReplayEvents || []);
        const seen = new Set(
          events
            .map((event) => event.workflow_type || event.workflowType)
            .filter(Boolean),
        );
        return WORKFLOW_CONTRACTS.every((contract) => seen.has(contract.workflow))
          ? [...seen].sort()
          : null;
      },
      "public replay did not render all airline workflow types",
      180_000,
    );
    evidence.workflowTypes = types;
    await page.screenshot({ path: path.join(SCREENSHOTS, "airline-replay-constellation.png"), fullPage: true });
    need(
      evidence.browserErrors.length === 0,
      `replay browser errors:\n${evidence.browserErrors.join("\n")}`,
    );
    evidence.result = "PASS";
    await writeJson("replay-summary.json", evidence);
    console.log(JSON.stringify(evidence, null, 2));
  } catch (error) {
    evidence.result = "FAIL";
    evidence.error = error.stack || error.message || String(error);
    await writeJson("replay-summary.json", evidence);
    throw error;
  } finally {
    await postJson("/api/blueprint/_demo_stream/stop").catch(() => {});
    await page.evaluate(() => window.__airlineReplaySource?.close()).catch(() => {});
    await context.close();
    await browser.close();
  }
}

async function runBackendRestartProbe() {
  await ensureEvidenceDirs();
  const evidence = {
    result: "PENDING",
    armedCursor: null,
    rewindObserved: false,
    browserErrors: [],
  };
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const page = await context.newPage();
  let armed = false;
  let recovered = false;
  page.on("pageerror", (error) => evidence.browserErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("favicon.ico")) {
      evidence.browserErrors.push(message.text());
    }
  });
  page.on("response", async (response) => {
    const match = response.url().match(/\/api\/world\/events\?after=(\d+)/);
    if (!match || response.status() >= 400) return;
    const cursor = Number(match[1]);
    if (cursor > 0) {
      armed = true;
      evidence.armedCursor = Math.max(evidence.armedCursor || 0, cursor);
    } else if (armed) {
      recovered = true;
      evidence.rewindObserved = true;
    }
  });
  try {
    await gotoUi(page, `${CONTROL_PLANE}/world`);
    await page.getByText("Synthetic Airline Hub Operations", { exact: false }).first().waitFor({
      timeout: UI_DEADLINE_MS,
    });
    await waitFor(() => armed || null, "world page did not advance its journal cursor", 30_000);
    await postJson("/api/world/reset", { seed: 42 });
    await waitFor(() => recovered || null, "mounted page did not rewind after backend restart", 120_000);
    await page.getByText("Synthetic Airline Hub Operations", { exact: false }).first().waitFor({
      timeout: UI_DEADLINE_MS,
    });
    need(evidence.browserErrors.length === 0, `restart browser errors:\n${evidence.browserErrors.join("\n")}`);
    evidence.result = "PASS";
    await writeJson("backend-restart-summary.json", evidence);
  } catch (error) {
    evidence.result = "FAIL";
    evidence.error = error.stack || error.message || String(error);
    await writeJson("backend-restart-summary.json", evidence);
    throw error;
  } finally {
    await context.close();
    await browser.close();
  }
}

async function runFunctionsDisabledProbe() {
  await ensureEvidenceDirs();
  const evidence = {
    result: "PENDING",
    browserErrors: [],
    expectedAborts: [],
    workflowCountBefore: 0,
    workflowCountAfter: 0,
  };
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const page = await context.newPage();
  installBrowserTracking(page, "functions-disabled", evidence);
  try {
    await gotoUi(page, `${CONTROL_PLANE}/world`);
    await page.getByText("Synthetic Airline Hub Operations", { exact: false }).first().waitFor({
      timeout: UI_DEADLINE_MS,
    });
    const before = await listWorkflows();
    evidence.workflowCountBefore = before.length;
    const response = await page.evaluate(async (scenario) => {
      const result = await fetch(`/api/world/scenarios/${scenario}`, { method: "POST" });
      return { status: result.status, body: await result.text() };
    }, WORKFLOW_CONTRACTS[0].scenario);
    need(response.status < 400, `Functions-disabled scenario returned HTTP ${response.status}`);
    await sleep(4_000);
    const after = await listWorkflows();
    evidence.workflowCountAfter = after.length;
    need(after.length === before.length, "Functions-disabled trigger created a phantom workflow");
    need(evidence.browserErrors.length === 0, `Functions-disabled browser errors:\n${evidence.browserErrors.join("\n")}`);
    evidence.result = "PASS";
    await writeJson("functions-disabled-summary.json", evidence);
  } catch (error) {
    evidence.result = "FAIL";
    evidence.error = error.stack || error.message || String(error);
    await writeJson("functions-disabled-summary.json", evidence);
    throw error;
  } finally {
    await context.close();
    await browser.close();
  }
}

async function runFunctionsRecoveryProbe() {
  await ensureEvidenceDirs();
  const contract = WORKFLOW_CONTRACTS[0];
  await postJson("/api/world/reset", { seed: 42 });
  const before = await listWorkflows();
  const known = new Set(before.map((item) => item.id));
  const scenario = await postJson(`/api/world/scenarios/${contract.scenario}`);
  need(scenario.ok, "Functions-recovery scenario was rejected");
  const workflow = await waitFor(
    async () => {
      const workflows = await listWorkflows();
      const item = workflows.find(
        (candidate) => candidate.type === contract.workflow && !known.has(candidate.id),
      );
      if (item?.status === "failed") throw new ProofError(workflowFailure(item));
      return item?.status === "completed" ? item : null;
    },
    "Functions host did not resume normal workflow execution",
    WORKFLOW_DEADLINE_MS,
  );
  await writeJson("functions-recovery-summary.json", {
    result: "PASS",
    workflowId: workflow.id,
    workflowType: workflow.type,
    status: workflow.status,
  });
}

async function runActorDisabledProbe() {
  await ensureEvidenceDirs();
  const world = await getJson("/api/world/state");
  need(world.enabled === false, "actor world is enabled during direct diagnostic probe");
  const evidence = { result: "PENDING", worldEnabled: world.enabled, workflows: {} };
  try {
    for (const contract of WORKFLOW_CONTRACTS) {
      const started = await postJson(
        `/api/world/diagnostics/${encodeURIComponent(contract.workflow)}`,
        { mode: "direct-diagnostic" },
      );
      const detail = await waitFor(
        async () => {
          const item = await getJson(`/api/workflows/${encodeURIComponent(started.workflow_id)}`);
          if (item.workflow.status === "failed") {
            throw new ProofError(workflowFailure(item.workflow));
          }
          return (
            item.workflow.status === "completed"
            && item.workflow.payload?.diagnostic
            && item.workflow.metadata?.diagnostic_only === true
          )
            ? item
            : null;
        },
        `disabled-world diagnostic did not complete for ${contract.workflow}`,
        WORKFLOW_DEADLINE_MS,
      );
      const diagnostic = detail.workflow.payload?.diagnostic;
      need(diagnostic?.actor_world_enabled === false, `${contract.workflow} claimed an enabled actor world`);
      need(
        diagnostic.source_sensor_event_id === started.source_sensor_event_id,
        `${contract.workflow} lost its diagnostic source sensor identity`,
      );
      need(detail.workflow.metadata?.diagnostic_only === true, `${contract.workflow} is not marked diagnostic-only`);
      need(detail.workflow.payload?.evidence?.command?.type === contract.command, `${contract.workflow} returned no typed command`);
      evidence.workflows[contract.workflow] = {
        workflowId: detail.workflow.id,
        status: detail.workflow.status,
        sourceSensorEventId: diagnostic.source_sensor_event_id,
        diagnosticOnly: true,
      };
    }
    evidence.result = "PASS";
    await writeJson("actor-disabled-summary.json", evidence);
  } catch (error) {
    evidence.result = "FAIL";
    evidence.error = error.stack || error.message || String(error);
    await writeJson("actor-disabled-summary.json", evidence);
    throw error;
  }
}

if (process.argv[2] === "--replay") {
  await runReplay();
} else if (process.argv[2] === "--backend-restart-probe") {
  await runBackendRestartProbe();
} else if (process.argv[2] === "--functions-disabled-probe") {
  await runFunctionsDisabledProbe();
} else if (process.argv[2] === "--functions-recovery-probe") {
  await runFunctionsRecoveryProbe();
} else if (process.argv[2] === "--actor-disabled-probe") {
  await runActorDisabledProbe();
} else {
  await runLive();
}
