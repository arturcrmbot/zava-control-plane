// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import ExecutionTimelineTab from "@client/components/apex/ExecutionTimelineTab";
import type { ExecutionTimelineRow, McpCall } from "@shared/types";

afterEach(cleanup);

const mixedTimeline: ExecutionTimelineRow[] = [
  {
    id: "workflow:WF-1",
    ts: 1_000,
    kind: "workflow",
    label: "workflow.started",
    status: "in_progress",
    currentPhase: "Validation",
    startedAt: 1_000,
  },
  {
    id: "phase:0:Validation",
    ts: 1_010,
    kind: "phase",
    label: "Validation",
    status: "completed",
    agentId: "deterministic-validator",
    startedAt: 1_000,
    completedAt: 1_010,
    durationMs: 10_000,
    toolCalls: [],
    spanIds: [],
  },
  {
    id: "reasoning:run-1",
    ts: 1_011,
    kind: "reasoning",
    label: "risk_reviewer",
    status: "completed",
    agent: "risk_reviewer",
    phase: "Validation",
    model: "gpt-4.1",
    messages: [{ role: "assistant", content: "Checked evidence" }],
    toolCalls: [{ tool: "screenVendor", result: { clear: true } }],
    extractedJson: { verdict: "amber" },
    tokensIn: 120,
    tokensOut: 30,
    costUsd: 0.0042,
    latencyMs: 1_000,
    durationMs: 1_000,
  },
  {
    id: "mcp:0:screenVendor:1012",
    ts: 1_012,
    kind: "tool",
    label: "screenVendor",
    status: "ok",
    mcpCallIndex: 0,
    tool: "screenVendor",
    method: "POST",
    url: "https://mcp.example.test/screen",
    statusCode: 200,
    durationMs: 25,
    timestamp: 1_012,
  },
  {
    id: "decision:decision-1",
    ts: 1_013,
    kind: "decision",
    label: "Approval",
    actor: "finance-director",
    personaRole: "finance-director",
    verdict: "approve",
    reason: "Evidence is complete",
    details: { evidence: { invoice: "INV-1" } },
  },
  {
    id: "ledger:child-1",
    ts: 1_014,
    kind: "agent",
    label: "workflow.sub_spawned",
    actor: "fleet-manager",
    actorKind: "agent",
    childWorkflowId: "W-CHILD-1",
    childWorkflowType: "vendor-kyc",
    details: {
      child_workflow_id: "W-CHILD-1",
      child_workflow_type: "vendor-kyc",
    },
  },
];

const mixedMcpCalls: McpCall[] = [{
  workflowId: "WF-1",
  timestamp: 1_012,
  tool: "screenVendor",
  method: "POST",
  url: "https://mcp.example.test/screen",
  request: { vendorId: "V-1", checks: ["sanctions"] },
  response: { clear: true, matches: [] },
  statusCode: 200,
  durationMs: 25,
}];

describe("ExecutionTimelineTab", () => {
  it("renders a customer-readable story for every mixed execution row", () => {
    render(<ExecutionTimelineTab timeline={mixedTimeline} />);

    expect(screen.getByText("Workflow started")).toBeTruthy();
    expect(screen.getByText("Validation")).toBeTruthy();
    expect(within(screen.getByTestId("execution-timeline-row-reasoning:run-1"))
      .getAllByText("Risk reviewer").length).toBeGreaterThan(0);
    expect(screen.getByText("Screen vendor")).toBeTruthy();
    expect(screen.getByText("Approval")).toBeTruthy();
    expect(screen.getByText("Vendor kyc child workflow started")).toBeTruthy();
    expect(screen.getByText("Finance director")).toBeTruthy();
    expect(screen.getByTestId("execution-timeline-row-mcp:0:screenVendor:1012").textContent)
      .toContain("25 ms");
  });

  it("expands persisted agent evidence without exposing a thought stream", () => {
    render(<ExecutionTimelineTab timeline={mixedTimeline} />);

    const row = screen.getByTestId("execution-timeline-row-reasoning:run-1");
    expect(row.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(row);

    expect(row.getAttribute("aria-expanded")).toBe("true");
    const details = screen.getByTestId("execution-timeline-details-reasoning:run-1");
    expect(details.textContent).toContain("gpt-4.1");
    expect(details.textContent).toContain("Validation");
    expect(details.textContent).toContain('"content": "Checked evidence"');
    expect(details.textContent).toContain('"tool": "screenVendor"');
    expect(details.textContent).toContain('"verdict": "amber"');
    expect(details.textContent).toContain("120");
    expect(details.textContent).toContain("30");
    expect(screen.queryByTestId("agent-thought-stream")).toBeNull();
  });

  it("expands the exact MCP request and response details", () => {
    render(
      <ExecutionTimelineTab
        timeline={mixedTimeline}
        mcpCalls={mixedMcpCalls}
      />,
    );

    fireEvent.click(screen.getByTestId("execution-timeline-row-mcp:0:screenVendor:1012"));

    const details = screen.getByTestId("execution-timeline-details-mcp:0:screenVendor:1012");
    expect(within(details).getByText("POST")).toBeTruthy();
    expect(details.textContent).toContain("https://mcp.example.test/screen");
    expect(details.textContent).toContain("200");
    expect(details.textContent).toContain('"vendorId": "V-1"');
    expect(details.textContent).toContain('"clear": true');
    expect(screen.queryByTestId("api-configuration")).toBeNull();
  });

  it("resolves expanded MCP evidence by persistent tool call identity", () => {
    const persistentRow: ExecutionTimelineRow = {
      ...mixedTimeline[3],
      id: "call-persisted-1",
      toolCallId: "call-persisted-1",
      mcpCallIndex: 0,
    };
    const reorderedCalls: McpCall[] = [
      {
        ...mixedMcpCalls[0],
        toolCallId: "other-call",
        request: { vendorId: "WRONG" },
        response: { clear: false },
      },
      {
        ...mixedMcpCalls[0],
        toolCallId: "call-persisted-1",
        request: { vendorId: "RIGHT" },
        response: { clear: true },
      },
    ];

    render(
      <ExecutionTimelineTab
        timeline={[persistentRow]}
        mcpCalls={reorderedCalls}
      />,
    );

    fireEvent.click(screen.getByTestId("execution-timeline-row-call-persisted-1"));

    const details = screen.getByTestId("execution-timeline-details-call-persisted-1");
    expect(details.textContent).toContain('"vendorId": "RIGHT"');
    expect(details.textContent).not.toContain('"vendorId": "WRONG"');
  });

  it("handles a missing canonical MCP call without crashing", () => {
    render(<ExecutionTimelineTab timeline={[mixedTimeline[3]]} />);

    fireEvent.click(screen.getByTestId("execution-timeline-row-mcp:0:screenVendor:1012"));

    expect(screen.getByTestId("execution-timeline-details-mcp:0:screenVendor:1012").textContent)
      .toContain("Tool evidence unavailable");
  });

  it("shows deterministic lifecycle, phase, and system evidence without claiming an agent ran", () => {
    const deterministic: ExecutionTimelineRow[] = [
      mixedTimeline[0],
      mixedTimeline[1],
      {
        id: "ledger:retry-1",
        ts: 1_011,
        kind: "system",
        label: "workflow.retry_scheduled",
        actor: "orchestrator",
        details: { attempt: 2, error: "upstream timeout" },
      },
    ];

    render(<ExecutionTimelineTab timeline={deterministic} />);

    expect(screen.getByText("Workflow started")).toBeTruthy();
    expect(screen.getByText("Validation")).toBeTruthy();
    expect(screen.getByText("Retry scheduled")).toBeTruthy();
    expect(screen.queryByText(/^Agent$/)).toBeNull();
  });

  it("renders exact deterministic output details as system evidence", () => {
    const output: ExecutionTimelineRow = {
      id: "output:decision",
      ts: 1_011,
      kind: "output",
      label: "decision.output",
      details: {
        command: {
          command_id: "cmd-1",
          type: "transfer_inventory",
          payload: { sku_id: "SKU-1", quantity: 24 },
        },
        reasoning: {
          summary: "Prepared transfer from journal-backed evidence.",
          authority: { persona: "merchandising_director", decision: "approve" },
        },
      },
    };

    render(<ExecutionTimelineTab timeline={[output]} />);

    const row = screen.getByTestId("execution-timeline-row-output:decision");
    expect(row.textContent).toContain("System");
    expect(row.textContent).toContain("Decision output");
    expect(row.textContent).not.toContain("Agent");
    expect(row.textContent).toContain("Prepared transfer from journal-backed evidence.");
    fireEvent.click(row);
    const details = screen.getByTestId("execution-timeline-details-output:decision");
    expect(details.textContent).toContain('"command_id": "cmd-1"');
    expect(details.textContent).toContain("Prepared transfer from journal-backed evidence.");
  });

  it("classifies workflow lifecycle rows even when backend kind is a ledger actor kind", () => {
    render(
      <ExecutionTimelineTab
        timeline={[
          {
            id: "ledger:completed-1",
            ts: 1_020,
            kind: "agent",
            label: "workflow.completed",
            status: "completed",
            actorKind: "agent",
            actor: "orchestrator",
          },
        ]}
      />,
    );

    expect(screen.getByText("Lifecycle")).toBeTruthy();
    expect(screen.getByText("Workflow completed")).toBeTruthy();
    expect(screen.queryByText(/^Agent$/)).toBeNull();
  });

  it("labels workflow.started as started rather than the workflow's terminal status", () => {
    render(
      <ExecutionTimelineTab
        timeline={[{
          id: "workflow:completed",
          ts: 1_000,
          kind: "workflow",
          label: "workflow.started",
          status: "completed",
        }]}
      />,
    );

    const row = screen.getByTestId("execution-timeline-row-workflow:completed");
    expect(within(row).getAllByText("Started").length).toBeGreaterThan(0);
    expect(within(row).queryByText("Completed")).toBeNull();
  });

  it("shows a neutral System executor for deterministic phases", () => {
    render(
      <ExecutionTimelineTab
        timeline={[{
          id: "phase:deterministic",
          ts: 1_010,
          kind: "phase",
          label: "Apply remediation",
          status: "completed",
          agentId: "system",
        }]}
      />,
    );

    const row = screen.getByTestId("execution-timeline-row-phase:deterministic");
    expect(row.textContent).toContain("System");
    expect(row.textContent).not.toContain("Finance agent");
  });

  it("keeps a failed agent labelled Error while expanding its diagnostics", () => {
    const failedAgent: ExecutionTimelineRow = {
      id: "reasoning:failed-agent",
      ts: 1_030,
      kind: "reasoning",
      label: "risk_reviewer failed",
      status: "failed",
      agent: "risk_reviewer",
      phase: "Validation",
      model: "gpt-4.1",
      skill: "risk-review",
      messages: [{ role: "assistant", content: "Unable to verify evidence" }],
      toolCalls: [{ tool: "screenVendor", success: false }],
      extractedJson: { error: "upstream timeout" },
      attributes: { "gen_ai.agent.name": "risk_reviewer" },
      details: { error: "upstream timeout" },
    };

    render(<ExecutionTimelineTab timeline={[failedAgent]} />);

    const row = screen.getByTestId("execution-timeline-row-reasoning:failed-agent");
    expect(within(row).getByText("Error")).toBeTruthy();
    expect(within(row).queryByText(/^Agent$/)).toBeNull();
    fireEvent.click(row);

    const details = screen.getByTestId("execution-timeline-details-reasoning:failed-agent");
    expect(details.textContent).toContain("gpt-4.1");
    expect(details.textContent).toContain('"content": "Unable to verify evidence"');
    expect(details.textContent).toContain('"tool": "screenVendor"');
    expect(details.textContent).toContain('"error": "upstream timeout"');
    expect(details.textContent).toContain('"gen_ai.agent.name": "risk_reviewer"');
  });

  it("explains when no execution evidence was captured", () => {
    render(<ExecutionTimelineTab timeline={[]} />);

    expect(screen.getByTestId("execution-timeline").textContent)
      .toContain("No execution evidence was captured");
  });
});
