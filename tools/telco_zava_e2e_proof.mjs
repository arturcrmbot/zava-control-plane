import { chromium } from "playwright";
import {
  mkdir,
  readdir,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

export const PROOF_CONTRACT = {
  evidence: [
    "summary.json",
    "world-journal.json",
    "durable-instances.json",
    "entity-graph.json",
    "recordings",
    "screenshots",
    "video",
  ],
  surfaces: [
    "world",
    "workflow-drawer",
    "memory",
    "knowledge",
    "ag-ui",
    "constellation",
  ],
  workflows: [
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
    "outage-risk-management",
    "predictive-site-maintenance",
    "field-repair-dispatch",
    "capacity-optimization",
    "service-ticket-resolution",
    "retention-orchestration",
  ],
};

if (process.argv[2] === "--print-contract") {
  console.log(JSON.stringify(PROOF_CONTRACT));
  process.exit(0);
}

async function waitForWorkflowTypes(types, knownByType, resolutions) {
  return waitFor(
    async () => {
      await resolveOpenExceptions(resolutions);
      const workflows = await listWorkflows();
      const selected = [];
      for (const type of types) {
        const known = knownByType.get(type) || new Set();
        const candidates = workflows
          .filter((workflow) => workflow.type === type && !known.has(workflow.id))
          .sort((left, right) => right.createdAt - left.createdAt);
        const failed = candidates.find((workflow) => workflow.status === "failed");
        if (failed) throw new ProofError(workflowFailure(failed));
        if (candidates[0]) selected.push(candidates[0]);
      }
      return selected.length === types.length ? selected : null;
    },
    `new workflows did not appear for: ${types.join(", ")}`,
    WORKFLOW_DEADLINE_MS,
  );
}

const API = (process.env.WORLD_API_BASE || "http://127.0.0.1:13101").replace(/\/$/, "");
const CONTROL_PLANE = (
  process.env.CONTROL_PLANE_BASE || "http://127.0.0.1:15273"
).replace(/\/$/, "");
const BLUEPRINT = (
  process.env.BLUEPRINT_BASE || "http://127.0.0.1:15275"
).replace(/\/$/, "");
const FUNCTIONS = (
  process.env.FUNCTIONS_HOST || "http://127.0.0.1:17171"
).replace(/\/$/, "");
const OUT_DIR = process.env.PROOF_OUT_DIR || "tmp/telco-zava-e2e-proof";
const SCREENSHOTS = path.join(OUT_DIR, "screenshots");
const VIDEO = path.join(OUT_DIR, "video");
const RECORDINGS = path.join(OUT_DIR, "recordings");
const POLL_MS = 500;
const WORKFLOW_DEADLINE_MS = 12 * 60 * 1000;
const UI_DEADLINE_MS = 45_000;

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
    metadata.failure_reason ||
    payload.reason ||
    payload.error ||
    `workflow ${workflow.id} failed`
  );
}

async function listWorkflows() {
  return getJson("/api/workflows");
}

async function waitForNewWorkflow(type, knownIds, statuses) {
  return waitFor(
    async () => {
      const workflows = await listWorkflows();
      const candidates = workflows
        .filter((workflow) => workflow.type === type && !knownIds.has(workflow.id))
        .sort((left, right) => right.createdAt - left.createdAt);
      const failed = candidates.find((workflow) => workflow.status === "failed");
      if (failed) throw new ProofError(workflowFailure(failed));
      return candidates.find((workflow) => statuses.includes(workflow.status)) || null;
    },
    `new ${type} workflow did not reach ${statuses.join("/")}`,
    WORKFLOW_DEADLINE_MS,
  );
}

async function resolveOpenExceptions(resolutions) {
  const exceptions = await getJson("/api/exceptions");
  for (const exception of exceptions) {
    const id = exception.id;
    if (!id || resolutions.some((entry) => entry.exceptionId === id)) continue;
    await postJson(`/api/exceptions/${encodeURIComponent(id)}/resolve`, {
      resolution: "approve",
      resolved_by: "telco-proof@zava.local",
    });
    resolutions.push({
      exceptionId: id,
      workflowId: exception.workflowId,
      resolution: "approve",
    });
  }
}

async function waitForCompleted(workflowIds, resolutions) {
  return waitFor(
    async () => {
      await resolveOpenExceptions(resolutions);
      const workflows = await listWorkflows();
      const selected = workflows.filter((workflow) => workflowIds.includes(workflow.id));
      const failed = selected.find((workflow) => workflow.status === "failed");
      if (failed) {
        const detail = await getJson(`/api/workflows/${encodeURIComponent(failed.id)}`);
        const ledgerFailure = (detail.workflow?.actionLedger || [])
          .filter((entry) => String(entry.action || "").includes("failed"))
          .at(-1);
        throw new ProofError(
          ledgerFailure?.details?.reason || workflowFailure(failed),
        );
      }
      return selected.length === workflowIds.length &&
        selected.every((workflow) => workflow.status === "completed")
        ? selected
        : null;
    },
    `workflows did not complete: ${workflowIds.join(", ")}`,
    WORKFLOW_DEADLINE_MS,
  );
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

async function openConstellation(context, evidence) {
  const page = await context.newPage();
  installBrowserTracking(page, "constellation", evidence);
  await page.goto(`${BLUEPRINT}/?view=constellation`);
  await page.locator("canvas").first().waitFor({ timeout: UI_DEADLINE_MS });
  await page
    .getByText("Live · org decisions and insights", { exact: true })
    .waitFor({ timeout: UI_DEADLINE_MS });
  await page.evaluate(() => {
    window.__telcoProofEvents = [];
    window.__telcoProofSource = new EventSource("/api/blueprint/stream");
    window.__telcoProofSource.addEventListener("event", (event) => {
      try {
        window.__telcoProofEvents.push(JSON.parse(event.data));
      } catch {
        // The proof checks parsed workflow events only.
      }
    });
  });
  return page;
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

async function assertLiveSurfaces(context, evidence, workflows, worldState, graph) {
  const page = await context.newPage();
  installBrowserTracking(page, "control-plane", evidence);
  await page.goto(`${CONTROL_PLANE}/world`);
  await page.getByTestId("telco-world-route").waitFor({ timeout: UI_DEADLINE_MS });
  await page.getByTestId("stat-sites").getByText("12 sites").waitFor();
  await page.getByTestId("stat-sessions").getByText("2200 sessions").waitFor();
  await page.getByTestId("stat-subscribers").getByText("2000 subscribers").waitFor();
  evidence.surfaces.world = {
    sites: await page.getByTestId("stat-sites").innerText(),
    sessions: await page.getByTestId("stat-sessions").innerText(),
    subscribers: await page.getByTestId("stat-subscribers").innerText(),
  };

  await page.getByRole("button", { name: "Orders", exact: true }).click();
  for (const orderId of evidence.ids.serviceOrders) {
    const orderCard = page
      .getByTestId("order-lens")
      .locator("article")
      .filter({ hasText: orderId });
    await orderCard.getByText(orderId, { exact: true }).waitFor();
    need(
      (await orderCard.innerText()).includes("activated at"),
      `Order lens did not show ${orderId} activated`,
    );
  }

  await page.getByRole("button", { name: "Customer Impact", exact: true }).click();
  await page.getByTestId("customer-impact-lens").waitFor();
  evidence.surfaces.customerImpactCards = await page
    .getByTestId("customer-impact-lens")
    .locator("article")
    .count();
  need(evidence.surfaces.customerImpactCards > 0, "Customer Impact lens is empty");
  await page.getByRole("button", { name: "Field Operations", exact: true }).click();
  await page.getByTestId("field-operations-lens").waitFor();
  evidence.surfaces.fieldOperations = await page
    .getByTestId("field-operations-lens")
    .innerText();
  need(
    evidence.surfaces.fieldOperations.includes("TECH-"),
    "Field Operations lens has no technicians",
  );
  await page.screenshot({
    path: path.join(SCREENSHOTS, "world.png"),
    fullPage: true,
  });

  evidence.surfaces.workflowDrawer = {};
  for (const workflow of workflows) {
    await page.goto(`${CONTROL_PLANE}/workflows/${workflow.id}`);
    await page.getByText(workflow.id, { exact: false }).first().waitFor();
    evidence.surfaces.workflowDrawer[workflow.id] = (
      await page.locator("body").innerText()
    ).includes(workflow.id);
  }

  const memoryIds = evidence.ids.workflowsByType;
  await page.goto(`${CONTROL_PLANE}/memory`);
  await page.getByRole("heading", { name: "Memory" }).waitFor();
  evidence.surfaces.memory = {};
  for (const [domain, workflowId] of Object.entries(memoryIds)) {
    await page.locator("select").selectOption(domain);
    await page.getByText(workflowId, { exact: false }).waitFor();
    evidence.surfaces.memory[domain] = workflowId;
  }
  await page.screenshot({
    path: path.join(SCREENSHOTS, "memory.png"),
    fullPage: true,
  });

  await page.goto(`${CONTROL_PLANE}/knowledge`);
  await page.getByRole("heading", { name: "Knowledge" }).waitFor();
  const summary = page.getByText(/[1-9]\d* nodes · [1-9]\d* edges/);
  await summary.waitFor({ timeout: UI_DEADLINE_MS });
  evidence.surfaces.knowledge = await summary.innerText();
  const graphIds = new Set(Object.keys(graph.workflowNodes || {}));
  for (const workflow of workflows) {
    need(graphIds.has(workflow.id), `Knowledge graph missing ${workflow.id}`);
  }
  await page.screenshot({
    path: path.join(SCREENSHOTS, "knowledge.png"),
    fullPage: true,
  });

  const run = await context.newPage();
  installBrowserTracking(run, "ag-ui", evidence);
  evidence.surfaces.agui = {};
  for (const workflow of workflows) {
    await run.goto(`${BLUEPRINT}/?view=run&run_id=${workflow.id}`);
    await run.getByTestId("run-panel").waitFor();
    await run
      .getByText(`Workflow run: ${workflow.id}`, { exact: true })
      .waitFor();
    await run.getByText("finished", { exact: true }).waitFor();
    evidence.surfaces.agui[workflow.id] = "finished";
  }
  await run.screenshot({
    path: path.join(SCREENSHOTS, "ag-ui.png"),
    fullPage: true,
  });

  need(worldState.notifications.length > 0, "world contains no care notifications");
  need(worldState.credits.length > 0, "world contains no care credits");
}

async function runLive() {
  await ensureEvidenceDirs();
  const evidence = {
    result: "PENDING",
    contract: PROOF_CONTRACT,
    ids: {},
    surfaces: {},
    workflowApi: {},
    durable: {},
    recorder: {},
    approvals: [],
    browserErrors: [],
    expectedAborts: [],
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

    const initial = await listWorkflows();
    const knownByType = new Map(
      PROOF_CONTRACT.workflows.map((type) => [
        type,
        new Set(
          initial
            .filter((workflow) => workflow.type === type)
            .map((workflow) => workflow.id),
        ),
      ]),
    );
    const initialWorld = await getJson("/api/world/state");
    const initialOrderIds = new Set(
      (initialWorld.orders || []).map((order) => order.id),
    );
    const happyOrder = await postJson("/api/world/service-orders", {
      account_id: "ACC-00001",
      product: "fiber-1gb",
      requested_site_id: "SITE-01",
    });
    const scenarios = {};
    for (const name of [
      "storm-cascade",
      "maintenance-save",
      "capacity-revenue",
      "vulnerable-retention",
    ]) {
      scenarios[name] = await postJson(`/api/world/scenarios/${name}`);
      need(scenarios[name].ok, `${name} scenario was rejected`);
    }
    const appeared = await waitForWorkflowTypes(
      PROOF_CONTRACT.workflows,
      knownByType,
      evidence.approvals,
    );
    const completed = await waitForCompleted(
      appeared.map((workflow) => workflow.id),
      evidence.approvals,
    );
    const primary = PROOF_CONTRACT.workflows.map((type) => {
      const workflow = completed.find((candidate) => candidate.type === type);
      need(workflow, `completed workflow missing for ${type}`);
      return workflow;
    });
    const workflowsByType = Object.fromEntries(
      primary.map((workflow) => [workflow.type, workflow.id]),
    );
    const postScenarioWorld = await getJson("/api/world/state");
    const serviceOrders = (postScenarioWorld.orders || [])
      .filter((order) => !initialOrderIds.has(order.id))
      .map((order) => order.id);

    evidence.ids = {
      workflowsByType,
      scenarios,
      capacitySite: "SITE-12",
      serviceOrders,
      happyOrder: happyOrder.order_id,
    };

    const details = {};
    for (const workflow of primary) {
      const detail = await getJson(`/api/workflows/${encodeURIComponent(workflow.id)}`);
      details[workflow.id] = detail;
      evidence.workflowApi[workflow.id] = {
        type: detail.workflow.type,
        status: detail.workflow.status,
        phase: detail.workflow.currentPhase,
        phases: detail.phases.map((phase) => phase.name),
      };
      const instanceId = detail.workflow.orchestrationInstanceId;
      need(instanceId, `${workflow.id} has no Durable instance ID`);
      evidence.durable[workflow.id] = await fetchDurable(instanceId);
    }

    const worldState = await getJson("/api/world/state");
    const worldJournal = await getJson("/api/world/events?after=0");
    const graph = await getJson("/api/entities/_graph?limit=2000");
    need(
      graph.nodes.length > 0 && graph.edges.length > 0,
      "Knowledge graph has no connected topology",
    );
    graph.workflowNodes = {};
    for (const workflow of primary) {
      const node = await getJson(
        `/api/entities/${encodeURIComponent(workflow.id)}`,
      );
      need(
        node.id === workflow.id && node._label === "Workflow",
        `entity graph did not persist Workflow ${workflow.id}`,
      );
      graph.workflowNodes[workflow.id] = node;
    }
    const activated = new Set(
      worldState.orders
        .filter((order) => order.status === "activated")
        .map((order) => order.id),
    );
    for (const orderId of evidence.ids.serviceOrders) {
      need(activated.has(orderId), `world order ${orderId} is not activated`);
    }
    need(
      worldState.sites.find((site) => site.id === "SITE-02")?.status === "healthy",
      "SITE-02 did not recover",
    );
    need(
      worldState.sessions.some((session) => session.status === "rerouted"),
      "world contains no rerouted sessions",
    );
    const capacitySite = worldState.sites.find(
      (site) => site.id === evidence.ids.capacitySite,
    );
    need(
      capacitySite?.status === "healthy" && capacitySite.utilization <= 0.85,
      `${evidence.ids.capacitySite} did not regain safe capacity headroom`,
    );
    need(
      worldJournal.events.some(
        (event) =>
          event.type === "site.capacity_constrained" &&
          event.actor_id === evidence.ids.capacitySite,
      ),
      `world journal has no capacity evidence for ${evidence.ids.capacitySite}`,
    );

    await waitFor(
      async () => {
        const events = await constellation.evaluate(
          () => window.__telcoProofEvents || [],
        );
        return primary.every((workflow) =>
          events.some(
            (event) =>
              event.workflow_id === workflow.id ||
              event.workflowId === workflow.id,
          ),
        )
          ? events
          : null;
      },
      "Constellation stream did not observe every workflow ID",
      60_000,
    );
    const streamEvents = await constellation.evaluate(
      () => window.__telcoProofEvents || [],
    );
    evidence.surfaces.constellation = Object.fromEntries(
      primary.map((workflow) => [
        workflow.id,
        streamEvents
          .filter(
            (event) =>
              event.workflow_id === workflow.id ||
              event.workflowId === workflow.id,
          )
          .map((event) => event.type),
      ]),
    );
    await constellation.screenshot({
      path: path.join(SCREENSHOTS, "constellation-live.png"),
      fullPage: true,
    });

    await assertLiveSurfaces(context, evidence, primary, worldState, graph);
    evidence.recorder.stop = await postJson("/api/blueprint/_recorder/stop");
    recorderStarted = false;
    evidence.recorder.files = (await readdir(RECORDINGS)).sort();
    for (const type of PROOF_CONTRACT.workflows) {
      need(
        evidence.recorder.files.some((name) => name.startsWith(`${type}-`)),
        `recorder produced no ${type} replay`,
      );
    }

    await writeJson("world-state.json", worldState);
    await writeJson("world-journal.json", worldJournal);
    await writeJson("durable-instances.json", evidence.durable);
    await writeJson("entity-graph.json", graph);
    await writeJson("workflow-details.json", details);
    need(
      evidence.browserErrors.length === 0,
      `browser errors:\n${evidence.browserErrors.join("\n")}`,
    );
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
      await constellation
        .evaluate(() => window.__telcoProofSource?.close())
        .catch(() => {});
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
  };
  const recordings = await readdir(RECORDINGS);
  for (const type of PROOF_CONTRACT.workflows) {
    need(
      recordings.some((name) => name.startsWith(`${type}-`)),
      `replay input missing ${type}`,
    );
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

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const page = await context.newPage();
  installBrowserTracking(page, "replay", evidence);
  try {
    await page.goto(`${BLUEPRINT}/?view=constellation`);
    await page.locator("canvas").first().waitFor({ timeout: UI_DEADLINE_MS });
    await page.evaluate(() => {
      window.__telcoReplayEvents = [];
      window.__telcoReplaySource = new EventSource("/api/blueprint/stream");
      window.__telcoReplaySource.addEventListener("event", (event) => {
        try {
          window.__telcoReplayEvents.push(JSON.parse(event.data));
        } catch {
          // Ignore keep-alives and malformed non-workflow messages.
        }
      });
    });
    await postJson("/api/blueprint/_demo_stream/start");
    const types = await waitFor(
      async () => {
        const events = await page.evaluate(() => window.__telcoReplayEvents || []);
        const seen = new Set(
          events
            .map((event) => event.workflow_type || event.workflowType)
            .filter(Boolean),
        );
        return PROOF_CONTRACT.workflows.every((type) => seen.has(type))
          ? [...seen].sort()
          : null;
      },
      "public replay did not render every Telco domain",
      180_000,
    );
    evidence.workflowTypes = types;
    await page.screenshot({
      path: path.join(SCREENSHOTS, "constellation-replay.png"),
      fullPage: true,
    });
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
    await page.evaluate(() => window.__telcoReplaySource?.close()).catch(() => {});
    await context.close();
    await browser.close();
  }
}

if (process.argv[2] === "--replay") {
  await runReplay();
} else {
  await runLive();
}
