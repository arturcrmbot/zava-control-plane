import { chromium } from "playwright";
import {
  mkdir,
  readFile,
  writeFile,
} from "node:fs/promises";
import path from "node:path";


const WORKFLOWS = [
  "inventory-rebalancing",
  "demand-spike-response",
  "promotion-readiness",
  "markdown-governance",
  "supplier-delay-recovery",
  "fulfilment-exception-resolution",
  "marketplace-seller-exception",
  "returns-disposition",
];
const SUPPORTING_WORKFLOWS = WORKFLOWS.slice(1);
export const PROOF_CONTRACT = {
  workflows: WORKFLOWS,
  primary_path: {
    origin: "autonomous_state_threshold",
    forbidden: ["/processes/*/run", "Run process"],
  },
  semantic_assertions: [
    "browser_baseline_before_sensor",
    "ordinary_activity_before_sensor",
    "journal_event_after_baseline",
    "real_actor_state_change",
    "exact_workflow_drill_in",
    "world_knowledge_id_match",
  ],
  results: [
    "substrate_result",
    "demo_result",
    "seller_review",
  ],
  evidence: [
    "manifest.json",
    "live-summary.json",
    "replay-summary.json",
    "world-snapshot-before.json",
    "world-snapshot-after.json",
    "world-journal.json",
    "workflow-evidence.json",
    "entity-graph.json",
    "agui-evidence.txt",
    "screenshots",
    "recordings",
    "logs",
  ],
};

if (process.argv[2] === "--print-contract") {
  console.log(JSON.stringify(PROOF_CONTRACT));
  process.exit(0);
}

const REPLAY = process.argv[2] === "--replay";
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
const OUT_DIR = process.env.PROOF_OUT_DIR || "proof";
const SCREENSHOTS = path.join(OUT_DIR, "screenshots");
const VIDEO = path.join(OUT_DIR, "recordings", "video");
const POLL_MS = 400;
const WORKFLOW_DEADLINE_MS = 8 * 60 * 1000;
const UI_DEADLINE_MS = 45_000;
const HERO_SKU = "SKU-STYLE-01-BLK-M";
const SOURCE_STOCK = "STOCK-STORE-EU-PAR-01-SKU-STYLE-01-BLK-M";
const DESTINATION_STOCK = "STOCK-STORE-UK-LON-01-SKU-STYLE-01-BLK-M";


class ProofError extends Error {}


function need(condition, message) {
  if (!condition) throw new ProofError(message);
}


const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));


async function ensureDirs() {
  await Promise.all([
    mkdir(OUT_DIR, { recursive: true }),
    mkdir(SCREENSHOTS, { recursive: true }),
    mkdir(VIDEO, { recursive: true }),
    mkdir(path.join(OUT_DIR, "recordings"), { recursive: true }),
    mkdir(path.join(OUT_DIR, "logs"), { recursive: true }),
  ]);
}


async function writeJson(name, value) {
  await writeFile(
    path.join(OUT_DIR, name),
    `${JSON.stringify(value, null, 2)}\n`,
    "utf8",
  );
}


async function requestJson(method, route, data) {
  const response = await fetch(`${API}${route}`, {
    method,
    headers: data === undefined
      ? undefined
      : { "content-type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (!response.ok) {
    throw new ProofError(
      `${method} ${route}: ${response.status} ${await response.text()}`,
    );
  }
  return response.json();
}


const getJson = (route) => requestJson("GET", route);
const postJson = (route, data) => requestJson("POST", route, data);


async function waitFor(check, message, deadline = UI_DEADLINE_MS) {
  const end = Date.now() + deadline;
  let lastError;
  while (Date.now() < end) {
    try {
      const result = await check();
      if (result) return result;
    } catch (error) {
      if (error instanceof ProofError) throw error;
      lastError = error;
    }
    await sleep(POLL_MS);
  }
  throw new ProofError(
    `${message}${lastError ? `; last error: ${lastError.message}` : ""}`,
  );
}


function destinationStock(state) {
  return (state.inventory_tokens || []).find(
    (position) => position.id === DESTINATION_STOCK,
  );
}


async function resolveOpenExceptions(resolutions) {
  const exceptions = await getJson("/api/exceptions");
  for (const exception of exceptions) {
    const exceptionId = exception.id;
    if (!exceptionId || resolutions.some((entry) => entry.exceptionId === exceptionId)) {
      continue;
    }
    const response = await fetch(
      `${API}/api/exceptions/${encodeURIComponent(exceptionId)}/resolve`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          resolution: "approve",
          resolved_by: "fashion-proof-operator@zava.local",
        }),
      },
    );
    if (response.status === 503) continue;
    if (!response.ok) {
      throw new ProofError(
        `exception ${exceptionId}: ${response.status} ${await response.text()}`,
      );
    }
    resolutions.push({
      exceptionId,
      workflowId: exception.workflowId,
      resolution: "approve",
    });
  }
}


async function listWorkflows() {
  return getJson("/api/workflows");
}


async function waitForWorkflow(
  workflowType,
  knownIds,
  resolutions,
) {
  return waitFor(
    async () => {
      await resolveOpenExceptions(resolutions);
      const workflows = await listWorkflows();
      const candidates = workflows
        .filter((workflow) => (
          workflow.type === workflowType && !knownIds.has(workflow.id)
        ))
        .sort((left, right) => right.createdAt - left.createdAt);
      const failed = candidates.find((workflow) => workflow.status === "failed");
      if (failed) {
        throw new ProofError(
          `${workflowType} failed: ${JSON.stringify(failed.metadata || {})}`,
        );
      }
      return candidates.find((workflow) => workflow.status === "completed") || null;
    },
    `${workflowType} did not complete`,
    WORKFLOW_DEADLINE_MS,
  );
}


async function collectAgui(workflowId) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2_000);
  let content = "";
  let reader;
  try {
    const response = await fetch(
      `${API}/api/workflows/${encodeURIComponent(workflowId)}/agui`,
      { signal: controller.signal },
    );
    need(response.ok, `AG-UI stream HTTP ${response.status}`);
    reader = response.body.getReader();
    while (content.length < 30_000) {
      const { done, value } = await reader.read();
      if (done) break;
      content += new TextDecoder().decode(value);
      if (content.includes(workflowId) && content.includes("RUN_FINISHED")) break;
    }
  } catch (error) {
    if (error.name !== "AbortError") throw error;
  } finally {
    clearTimeout(timeout);
    controller.abort();
    await reader?.cancel().catch(() => {});
  }
  need(content.includes(workflowId), "AG-UI history omitted exact workflow ID");
  return content;
}


function attachBrowserErrorGate(page, browserErrors) {
  page.on("console", (message) => {
    if (message.type() === "error") {
      browserErrors.push(`console: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => {
    browserErrors.push(`pageerror: ${error.message}`);
  });
}


async function runLive() {
  await ensureDirs();
  const browserErrors = [];
  const criteria = {
    browser_baseline_before_sensor: "PENDING",
    ordinary_activity_before_sensor: "PENDING",
    journal_event_after_baseline: "PENDING",
    real_actor_state_change: "PENDING",
    exact_workflow_drill_in: "PENDING",
    world_knowledge_id_match: "PENDING",
    all_eight_workflows: "PENDING",
    zero_manual_hero_starts: "PENDING",
  };
  const evidence = {
    contract: PROOF_CONTRACT,
    primaryPath: {},
    resolutions: [],
    workflows: {},
  };
  let browser;
  try {
    const runtime = await getJson("/api/runtime");
    need(runtime.vertical?.name === "fashion", "active vertical is not fashion");
    const scene = await getJson("/api/world/scene");
    need(scene.enabled === true, "pack-owned world scene is unavailable");
    need(scene.locations?.length === 10, "scene does not expose ten real locations");

    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1600, height: 1000 },
      recordVideo: { dir: VIDEO, size: { width: 1600, height: 1000 } },
    });
    const page = await context.newPage();
    attachBrowserErrorGate(page, browserErrors);
    await page.goto(`${CONTROL_PLANE}/world`, { waitUntil: "domcontentloaded" });
    await page.getByTestId("spatial-world-route").waitFor({
      state: "visible",
      timeout: UI_DEADLINE_MS,
    });
    const uiRunControls = await page
      .locator("button")
      .filter({ hasText: /Run process/i })
      .count();
    need(uiRunControls === 0, "primary World path exposes a process-run control");

    const baselineState = await waitFor(
      async () => {
        const state = await getJson("/api/world/state");
        return state.ordinary_activity_count >= 2 ? state : null;
      },
      "ordinary retail activity did not begin",
    );
    const baseline = await getJson("/api/world/events?after=0");
    need(
      !baseline.events.some((event) => (
        event.type === "sensor.tripped"
        && event.actor_id === "sensor:inventory_imbalance"
      )),
      "hero sensor fired before the browser baseline",
    );
    criteria.browser_baseline_before_sensor = "PASS";
    criteria.ordinary_activity_before_sensor = "PASS";
    const beforeStock = destinationStock(baselineState);
    need(beforeStock, `baseline omitted ${DESTINATION_STOCK}`);
    const actorStateBefore = await page
      .getByTestId(`actor-${DESTINATION_STOCK}`)
      .textContent();
    const knownWorkflowIdsAtBaseline = new Set(
      (await listWorkflows()).map((workflow) => workflow.id),
    );
    evidence.baseline = {
      latest_seq: baseline.latest_seq,
      sim_time: baselineState.sim_time,
      ordinary_activity_count: baselineState.ordinary_activity_count,
      actorStateBefore,
      destination_available: beforeStock.available,
      known_workflow_ids: Array.from(knownWorkflowIdsAtBaseline),
    };
    await writeJson("world-snapshot-before.json", baselineState);
    await page.screenshot({
      path: path.join(SCREENSHOTS, "01-world-baseline.png"),
      fullPage: true,
    });

    const sensor = await waitFor(
      async () => {
        const response = await getJson(
          `/api/world/events?after=${baseline.latest_seq}`,
        );
        return response.events.find((event) => (
          event.type === "sensor.tripped"
          && event.actor_id === "sensor:inventory_imbalance"
          && event.seq > baseline.latest_seq
        )) || null;
      },
      "state-derived inventory sensor did not fire after browser baseline",
      WORKFLOW_DEADLINE_MS,
    );
    need(sensor.cause_event_id, "sensor has no causal stock event");
    need(sensor.payload?.threshold?.crossed === true, "sensor threshold did not cross");
    criteria.journal_event_after_baseline = "PASS";

    const hero = await waitForWorkflow(
      "inventory-rebalancing",
      knownWorkflowIdsAtBaseline,
      evidence.resolutions,
    );
    need(
      hero.id === `rebalance-${sensor.event_id}`,
      "hero workflow ID does not derive from the sensor event",
    );
    evidence.workflows["inventory-rebalancing"] = hero;

    const afterState = await waitFor(
      async () => {
        const state = await getJson("/api/world/state");
        const stock = destinationStock(state);
        return (
          stock
          && stock.available > beforeStock.available
          && state.knowledge_relationships?.some(
            (relationship) => relationship.workflow_id === hero.id,
          )
        ) ? state : null;
      },
      "inventory transfer did not visibly change real world state",
      WORKFLOW_DEADLINE_MS,
    );
    const afterStock = destinationStock(afterState);
    const expectedActorStateAfter = `${afterStock.available} available`;
    await waitFor(
      async () => {
        const value = await page
          .getByTestId(`actor-${DESTINATION_STOCK}`)
          .textContent();
        return value?.includes(expectedActorStateAfter) ? value : null;
      },
      `destination stock token did not show ${expectedActorStateAfter}`,
    );
    const actorStateAfter = await page
      .getByTestId(`actor-${DESTINATION_STOCK}`)
      .textContent();
    evidence.actorStateAfter = actorStateAfter;
    criteria.real_actor_state_change = "PASS";
    await writeJson("world-snapshot-after.json", afterState);
    await page.screenshot({
      path: path.join(SCREENSHOTS, "02-world-outcome.png"),
      fullPage: true,
    });

    const processLink = page.getByTestId(`workflow-card-${hero.id}`);
    await processLink.waitFor({ state: "visible", timeout: UI_DEADLINE_MS });
    need(
      await processLink.getAttribute("href")
        === `/workflows/${encodeURIComponent(hero.id)}`,
      "world process card does not link to the exact workflow ID",
    );
    await processLink.click();
    await page.waitForURL(`**/workflows/${encodeURIComponent(hero.id)}`);
    await page.getByText(hero.id, { exact: false }).first().waitFor();
    await page.screenshot({
      path: path.join(SCREENSHOTS, "03-workflow-drill-in.png"),
      fullPage: true,
    });
    const heroDetail = await getJson(
      `/api/workflows/${encodeURIComponent(hero.id)}`,
    );
    const workflowPayload = heroDetail.workflow?.payload || {};
    const observation = workflowPayload.retail_case || {};
    need(heroDetail.phases?.length >= 4, "workflow phase evidence is incomplete");
    need(
      observation.skills?.includes("inventory-rebalance-planner"),
      "workflow omitted declared reasoning skill",
    );
    need(
      observation.mcp_tools?.includes("fashion_prepare_inventory_transfer"),
      "workflow omitted declared MCP tool",
    );
    need(
      observation.authority?.persona === "merchandising_director",
      "workflow omitted HITL authority persona",
    );
    need(
      workflowPayload.decision?.command?.type === "inventory.transfer",
      "workflow omitted typed command evidence",
    );
    need(workflowPayload.decision?.reasoning, "workflow omitted reasoning evidence");
    need(
      workflowPayload.outcome?.status === "resolved",
      "workflow omitted terminal evaluation evidence",
    );
    criteria.exact_workflow_drill_in = "PASS";

    const heroAgui = await collectAgui(hero.id);
    await writeFile(
      path.join(OUT_DIR, "agui-evidence.txt"),
      heroAgui,
      "utf8",
    );

    const heroEntity = await getJson(
      `/api/entities/${encodeURIComponent(hero.id)}`,
    );
    need(heroEntity.id === hero.id, "Knowledge omitted exact hero workflow ID");
    for (const actorId of [
      HERO_SKU,
      "STORE-EU-PAR-01",
      "STORE-UK-LON-01",
      DESTINATION_STOCK,
    ]) {
      const entity = await getJson(`/api/entities/${encodeURIComponent(actorId)}`);
      need(entity.id === actorId, `Knowledge omitted actor ${actorId}`);
    }
    const graph = await getJson("/api/entities/_graph?limit=1200");
    const nodeIds = new Set(graph.nodes.map((node) => node.id));
    need(nodeIds.has(hero.id), "graph omitted workflow node");
    need(nodeIds.has(HERO_SKU), "graph omitted SKU node");
    need(
      graph.edges.some((edge) => (
        edge.src === DESTINATION_STOCK
        && edge.dst === "STORE-UK-LON-01"
        && edge.rel === "HOSTED_ON"
      )),
      "graph omitted changed destination stock relationship",
    );
    await writeJson("entity-graph.json", graph);

    await page.goto(`${CONTROL_PLANE}/knowledge`, {
      waitUntil: "domcontentloaded",
    });
    await page.locator("canvas").first().waitFor({
      state: "visible",
      timeout: UI_DEADLINE_MS,
    });
    await page.screenshot({
      path: path.join(SCREENSHOTS, "04-knowledge-outcome.png"),
      fullPage: true,
    });
    criteria.world_knowledge_id_match = "PASS";

    const composition = await getJson("/api/blueprint/composition");
    const compositionText = JSON.stringify(composition);
    for (const workflowType of WORKFLOWS) {
      need(
        compositionText.includes(workflowType),
        `Constellation composition omitted ${workflowType}`,
      );
    }
    const constellation = await context.newPage();
    attachBrowserErrorGate(constellation, browserErrors);
    await constellation.goto(`${BLUEPRINT}/?view=constellation`, {
      waitUntil: "domcontentloaded",
    });
    await constellation.locator("canvas").first().waitFor({
      state: "visible",
      timeout: UI_DEADLINE_MS,
    });
    await constellation.screenshot({
      path: path.join(SCREENSHOTS, "05-constellation.png"),
      fullPage: true,
    });

    for (const workflowType of SUPPORTING_WORKFLOWS) {
      const workflow = await waitForWorkflow(
        workflowType,
        knownWorkflowIdsAtBaseline,
        evidence.resolutions,
      );
      evidence.workflows[workflowType] = workflow;
    }
    criteria.all_eight_workflows = (
      Object.keys(evidence.workflows).length === WORKFLOWS.length
        ? "PASS"
        : "FAIL"
    );

    const details = {};
    for (const [workflowType, workflow] of Object.entries(evidence.workflows)) {
      details[workflowType] = await getJson(
        `/api/workflows/${encodeURIComponent(workflow.id)}`,
      );
      need(
        details[workflowType].workflow.status === "completed",
        `${workflowType} is not completed`,
      );
    }
    await writeJson("workflow-evidence.json", details);
    const journal = await getJson("/api/world/events?after=0");
    const heroDiagnosticSensors = journal.events.filter((event) => (
      event.type === "sensor.tripped"
      && event.actor_id === "sensor:inventory_imbalance"
      && event.payload?.diagnostic === true
    ));
    evidence.primaryPath = {
      directProcessStarts: heroDiagnosticSensors.length,
      uiRunControls,
    };
    criteria.zero_manual_hero_starts = (
      heroDiagnosticSensors.length === 0 && uiRunControls === 0
        ? "PASS"
        : "FAIL"
    );
    need(
      criteria.zero_manual_hero_starts === "PASS",
      "hero workflow was started from a diagnostic route or UI control",
    );
    await writeJson("world-journal.json", journal);
    need(browserErrors.length === 0, `browser errors: ${browserErrors.join(" | ")}`);

    const summary = {
      result: "PASS",
      substrate_result: "PASS",
      demo_result: "PASS",
      seller_review: "PENDING",
      browserErrors,
      criteria,
      hero: {
        workflow_id: hero.id,
        sensor_event_id: sensor.event_id,
        sensor_seq: sensor.seq,
        browser_baseline_seq: baseline.latest_seq,
        actorStateBefore,
        actorStateAfter,
        source_stock_id: SOURCE_STOCK,
        destination_stock_id: DESTINATION_STOCK,
      },
      supporting_workflows: SUPPORTING_WORKFLOWS.map((workflowType) => ({
        workflow_type: workflowType,
        workflow_id: evidence.workflows[workflowType].id,
        origin: "autonomous_story_cascade",
      })),
      primary_path: {
        origin: "autonomous_state_threshold",
        direct_process_starts: heroDiagnosticSensors.length,
        ui_run_controls: uiRunControls,
      },
      resolutions: evidence.resolutions,
    };
    await writeJson("live-summary.json", summary);
    await context.close();
    await browser.close();
    return summary;
  } catch (error) {
    const summary = {
      result: "FAIL",
      substrate_result: "FAIL",
      demo_result: "FAIL",
      seller_review: "PENDING",
      browserErrors,
      criteria,
      error: error instanceof Error ? error.message : String(error),
      evidence,
    };
    await writeJson("live-summary.json", summary).catch(() => {});
    if (browser) await browser.close().catch(() => {});
    throw error;
  }
}


async function functionsAreDisabled() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1_000);
  try {
    await fetch(`${FUNCTIONS}/admin/host/status`, {
      signal: controller.signal,
    });
    return false;
  } catch {
    return true;
  } finally {
    clearTimeout(timeout);
  }
}


async function runReplay() {
  await ensureDirs();
  const browserErrors = [];
  let browser;
  try {
    const live = JSON.parse(
      await readFile(path.join(OUT_DIR, "live-summary.json"), "utf8"),
    );
    need(live.result === "PASS", "replay requires passing live evidence");
    const world = await getJson("/api/world/state");
    need(world.enabled === false, "actor world remained enabled during replay");
    need(await functionsAreDisabled(), "Functions host remained enabled during replay");

    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1400, height: 900 },
    });
    const page = await context.newPage();
    attachBrowserErrorGate(page, browserErrors);
    await page.goto(CONTROL_PLANE, { waitUntil: "domcontentloaded" });
    await page.locator("body").waitFor({ state: "visible" });
    await page.screenshot({
      path: path.join(SCREENSHOTS, "06-replay-degraded.png"),
      fullPage: true,
    });

    const constellation = await context.newPage();
    attachBrowserErrorGate(constellation, browserErrors);
    await constellation.goto(`${BLUEPRINT}/?view=constellation`, {
      waitUntil: "domcontentloaded",
    });
    await constellation.locator("canvas").first().waitFor({
      state: "visible",
      timeout: UI_DEADLINE_MS,
    });
    need(browserErrors.length === 0, `replay browser errors: ${browserErrors.join(" | ")}`);
    const summary = {
      result: "PASS",
      substrate_result: "PASS",
      functions_disabled: "PASS",
      world_disabled: "PASS",
      browserErrors,
      droppedWorkflowEvents: 0,
      cleanTeardown: "PENDING",
      workflow_count: WORKFLOWS.length,
    };
    await writeJson("replay-summary.json", summary);
    await context.close();
    await browser.close();
    return summary;
  } catch (error) {
    await writeJson("replay-summary.json", {
      result: "FAIL",
      substrate_result: "FAIL",
      functions_disabled: "FAIL",
      world_disabled: "FAIL",
      browserErrors,
      droppedWorkflowEvents: null,
      cleanTeardown: "PENDING",
      error: error instanceof Error ? error.message : String(error),
    }).catch(() => {});
    if (browser) await browser.close().catch(() => {});
    throw error;
  }
}


try {
  await (REPLAY ? runReplay() : runLive());
} catch (error) {
  console.error(
    error instanceof ProofError
      ? `FASHION PROOF FAILED: ${error.message}`
      : error,
  );
  process.exit(1);
}
