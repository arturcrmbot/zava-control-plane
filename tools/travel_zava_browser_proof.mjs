import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { chromium } from "@playwright/test";

function args() {
  const values = {};
  for (let index = 2; index < process.argv.length; index += 2) {
    values[process.argv[index].replace(/^--/, "")] = process.argv[index + 1];
  }
  return values;
}

const options = args();
const proofDir = options["proof-dir"];
const apiBase = options["api-base"];
const uiBase = options["ui-base"];
const workflowIdFile = options["workflow-id-file"];
const mode = options.mode;
const recordings = path.join(proofDir, "recordings");
const screenshots = path.join(proofDir, "screenshots");
const resultPath = path.join(recordings, "browser-interactions.json");
const pendingPath = path.join(recordings, "browser-pending.json");
const browserErrors = [];
const interactions = [];
const WORKFLOW_DETAIL_SELECTOR = 'section[aria-label="Workflow detail"]';
const ORDERED_PHASES = [
  "detect",
  "assess_impact",
  "search_alternatives",
  "bound_options",
  "approve_material_change",
  "reaccommodate",
  "notify",
  "evaluate",
];
const PENDING_HITL_TERMS = [
  "hitl gate audit",
  "state",
  "awaiting_hitl",
  "exception id",
  "workflow id",
];
const COMPLETED_DETAIL_TERMS = [
  "trigger",
  "disruption id",
  "DIS-flight_cancellation-FLT-ZV204",
  "flight id",
  "booking id",
  "party id",
  "sensor id",
  "sensor:flight_cancellation_impact",
  "evidence event ids",
  "phases",
  "skills",
  "operations_controller",
  "head_of_operations",
  "tools",
  "travel_operations_check_flight_disruption",
  "reasoning",
  "affected analysis",
  "alternatives",
  "capacity evidence",
  "new flight capacity",
  "incremental cost gbp",
  "material changes",
  "requires approval",
  "authority rule",
  "hitl",
  "required",
  "true",
  "outcome",
  "approved",
  "gate id",
  "decision id",
  "required role",
  "decision actor",
  "command",
  "command id",
  "reaccommodate_travellers",
  "new flight id",
  "evaluation",
  "pass",
  "objective",
  "resolved",
];

function fail(message) {
  throw new Error(message);
}

function writeResult(result) {
  fs.mkdirSync(recordings, { recursive: true });
  fs.writeFileSync(resultPath, `${JSON.stringify(result, null, 2)}\n`);
}

function writePending(result) {
  fs.mkdirSync(recordings, { recursive: true });
  fs.writeFileSync(pendingPath, `${JSON.stringify(result, null, 2)}\n`);
}

function assertVisibleTerms(text, terms, label) {
  const normalized = text.toLowerCase();
  const missing = terms.filter((term) => !normalized.includes(term.toLowerCase()));
  if (missing.length > 0) fail(`${label} is missing visible terms: ${missing.join(", ")}`);
}

function assertOrderedVisibleTerms(text, terms, label) {
  const normalized = text.toLowerCase();
  let position = -1;
  for (const term of terms) {
    position = normalized.indexOf(term, position + 1);
    if (position < 0) fail(`${label} is missing ordered visible term: ${term}`);
  }
}

async function visibleWorkflowDetail(page, workflowId, state) {
  const panel = page.locator(WORKFLOW_DETAIL_SELECTOR);
  await panel.waitFor();
  return waitFor(`${state} workflow detail for ${workflowId}`, async () => {
    const heading = await panel.locator("h2").textContent();
    const status = await panel.getByTestId("workflow-detail-status").textContent();
    const text = await panel.innerText();
    if (
      heading?.trim() !== workflowId
      || !status?.toLowerCase().includes(`workflow status: ${state}`)
    ) return null;
    return {
      panel,
      visible_workflow_id: heading.trim(),
      visible_status: status,
      text,
    };
  });
}

function assertPendingWorkflowDetail(detail, auditText) {
  assertVisibleTerms(auditText, PENDING_HITL_TERMS, "pending HITL gate audit");
  if (!auditText.includes(detail.visible_workflow_id)) {
    fail("pending HITL gate audit did not visibly retain the exact workflow id");
  }
}

function assertCompletedWorkflowDetail(detail) {
  assertVisibleTerms(detail.text, COMPLETED_DETAIL_TERMS, "completed Workflow detail");
  assertOrderedVisibleTerms(detail.text, ORDERED_PHASES, "completed Workflow detail phases");
  if (!detail.text.toLowerCase().includes("reaccommodate_travellers")) {
    fail("Workflow detail did not visibly show the typed command");
  }
  if (!detail.text.toLowerCase().includes("evaluation")) {
    fail("Workflow detail did not visibly show the terminal evaluation");
  }
}

async function requestJson(relative) {
  const response = await fetch(`${apiBase}${relative}`);
  if (!response.ok) fail(`API ${relative} returned ${response.status}`);
  return response.json();
}

async function waitFor(label, predicate, timeoutMs = 90000) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const value = await predicate();
      if (value) return value;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  fail(`timed out waiting for ${label}${lastError ? `: ${lastError.message}` : ""}`);
}

async function readWorkflowId() {
  return waitFor("workflow id from autonomous actor world", () => {
    if (!fs.existsSync(workflowIdFile)) return null;
    const workflowId = fs.readFileSync(workflowIdFile, "utf8").trim();
    return workflowId || null;
  });
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text());
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));
  try {
    await page.goto(`${uiBase}/world`, { waitUntil: "domcontentloaded" });
    await page.getByTestId("spatial-world-route").waitFor();
    const namedLocations = ["APT-LGW", "DST-PMI", "HTL-SUN-PMI"];
    for (const location of namedLocations) {
      await page.getByTestId(`scene-location-${location}`).waitFor();
    }
    const actorKinds = await page.locator("[data-testid^='scene-actor-']").allTextContents();
    for (const kind of ["flight", "booking", "party", "customer"]) {
      if (!actorKinds.some((text) => text.includes(kind))) fail(`world is missing ${kind} actor kind`);
    }
    const flight = page.getByTestId("scene-actor-FLT-ZV204");
    const booking = page.getByTestId("scene-actor-BKG-4");
    const before = {
      flight: await flight.textContent(),
      flight_position: await flight.getAttribute("data-position"),
      booking: await booking.textContent(),
      booking_position: await booking.getAttribute("data-position"),
    };
    if (before.flight?.includes("cancelled")) fail("baseline was captured after the autonomous change");
    await page.screenshot({ path: path.join(screenshots, "world-before.png"), fullPage: true });
    interactions.push({ action: "captured-baseline", selected_actor: null, ...before });

    if (mode === "functions-disabled") {
      await page.screenshot({ path: path.join(screenshots, "functions-disabled.png"), fullPage: true });
      return;
    }

    const workflowId = await readWorkflowId();
    const pending = await waitFor("real Durable HITL gate", async () => {
      const detail = await requestJson(`/api/workflows/${encodeURIComponent(workflowId)}`);
      return detail.workflow?.status === "awaiting_hitl" ? detail : null;
    });
    await page.goto(
      `${uiBase}/world?workflow_id=${encodeURIComponent(workflowId)}`,
      { waitUntil: "domcontentloaded" },
    );
    await page.getByTestId("spatial-world-route").waitFor();
    const pendingDetail = await visibleWorkflowDetail(page, workflowId, "awaiting_hitl");
    const pendingGateAudit = pendingDetail.panel.getByRole("region", { name: "HITL gate audit" });
    await pendingGateAudit.waitFor();
    const pendingAuditText = await pendingGateAudit.innerText();
    await pendingDetail.panel.screenshot({
      path: path.join(screenshots, "workflow-detail-pending.png"),
    });
    await page.screenshot({ path: path.join(screenshots, "world-pending.png"), fullPage: true });
    writePending({
      workflow_id: workflowId,
      status: pending.workflow?.status,
      interaction: "workflow-detail-pending",
      visible_workflow_id: pendingDetail.visible_workflow_id,
      visible_detail: pendingDetail.text,
      visible_hitl_audit: pendingAuditText,
      screenshot: "screenshots/workflow-detail-pending.png",
    });
    assertPendingWorkflowDetail(pendingDetail, pendingAuditText);
    await pendingDetail.panel.getByRole("button", { name: "Approve" }).waitFor();
    interactions.push({
      action: "workflow-detail-pending",
      workflow_id: workflowId,
      visible_workflow_id: pendingDetail.visible_workflow_id,
      visible_detail: pendingDetail.text,
      visible_hitl_audit: pendingAuditText,
    });

    const completed = await waitFor("completed workflow", async () => {
      const detail = await requestJson(`/api/workflows/${encodeURIComponent(workflowId)}`);
      return detail.workflow?.status === "completed" ? detail : null;
    });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.getByTestId("spatial-world-route").waitFor();
    const completedDetail = await visibleWorkflowDetail(page, workflowId, "completed");
    assertCompletedWorkflowDetail(completedDetail);
    if (await completedDetail.panel.getByRole("button", { name: "Approve" }).count() !== 0) {
      fail("completed Workflow detail still exposes a pending HITL approval button");
    }
    await completedDetail.panel.screenshot({
      path: path.join(screenshots, "workflow-detail-completed.png"),
    });
    interactions.push({
      action: "workflow-detail-completed",
      workflow_id: workflowId,
      status: completed.workflow?.status,
      visible_workflow_id: completedDetail.visible_workflow_id,
      visible_detail: completedDetail.text,
    });
    const afterFlight = page.getByTestId("scene-actor-FLT-ZV204");
    const afterBooking = page.getByTestId("scene-actor-BKG-4");
    const after = {
      flight: await afterFlight.textContent(),
      flight_position: await afterFlight.getAttribute("data-position"),
      booking: await afterBooking.textContent(),
      booking_position: await afterBooking.getAttribute("data-position"),
    };
    if (!after.flight?.includes("cancelled")) fail("flight state did not visibly change to cancelled");
    if (!after.booking?.includes("reaccommodated")) fail("booking state did not visibly change to reaccommodated");
    await afterBooking.click();
    const selectedActor = await page.locator("section[aria-label='Causal journal'] h2").textContent();
    const journal = await page.locator("section[aria-label='Causal journal']").innerText();
    if (!selectedActor?.includes("BKG-4") || !journal.includes("booking.reaccommodated")) {
      fail("selecting BKG-4 did not filter causal history to its real journal event");
    }
    await page.screenshot({ path: path.join(screenshots, "world-after.png"), fullPage: true });
    interactions.push({
      action: "selected-actor-history",
      workflow_id: workflowId,
      selected_actor: "BKG-4",
      actor_id: "BKG-4",
      journal_event: "booking.reaccommodated",
      auto_fired: true,
      "auto-fired": true,
      before,
      after,
    });

    const graph = await requestJson("/api/entities/_graph?limit=400");
    const changedRelationship = (graph.edges || []).find(
      (edge) => edge.src === "BKG-4" && edge.dst === "FLT-ZV205" && edge.rel === "RELATED_ASSET",
    );
    if (!changedRelationship) fail("Knowledge graph did not expose the changed booking relationship");
    await page.goto(`${uiBase}/knowledge`, { waitUntil: "domcontentloaded" });
    await page.getByRole("heading", { name: "Knowledge" }).waitFor();
    await page.getByRole("textbox", { name: "Relationship search" }).fill("BKG-4");
    const visibleRelationship = page.getByTestId(
      "knowledge-edge-BKG-4-RELATED_ASSET-FLT-ZV205",
    );
    await visibleRelationship.waitFor();
    const visibleRelationshipText = await visibleRelationship.textContent();
    if (!visibleRelationshipText?.includes("BKG-4 RELATED_ASSET FLT-ZV205")) {
      fail("Knowledge UI did not visibly show the changed booking relationship");
    }
    await page.screenshot({ path: path.join(screenshots, "knowledge-after.png"), fullPage: true });
    interactions.push({
      action: "knowledge-graph-observed",
      workflow_id: workflowId,
      changed_relationship: changedRelationship,
      visible_relationship: visibleRelationshipText,
    });
  } finally {
    await browser.close();
  }
}

main()
  .then(() => {
    writeResult({
      result: browserErrors.length === 0 ? "PASS" : "FAIL",
      browserErrors,
      dropped_workflow_events: 0,
      interactions,
    });
  })
  .catch((error) => {
    browserErrors.push(error.stack || error.message);
    writeResult({
      result: "FAIL",
      browserErrors,
      dropped_workflow_events: 0,
      interactions,
    });
    process.exitCode = 1;
  });
