import { defineTool } from "@github/copilot-sdk";
import { z } from "zod";
import type { StateStore } from "@server/services/stateStore";

const SCOPE_DAYS_DEFAULT = 30;

export interface DryRunPolicyArgs {
  policyId: string;
  proposedValue: unknown;
  scopeDays?: number;
}

export async function dryRunPolicyImpl(
  store: StateStore,
  { policyId, proposedValue, scopeDays }: DryRunPolicyArgs
): Promise<{
  scopeDays: number;
  totalEvaluated: number;
  wouldBeDifferent: number;
  impactedWorkflowIds: string[];
}> {
  const days = scopeDays ?? SCOPE_DAYS_DEFAULT;
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;

  const completed = store.listWorkflows({ status: "completed" }).filter(
    w => w.createdAt >= cutoff
  );

  let wouldBeDifferent = 0;
  const impactedWorkflowIds: string[] = [];

  if (policyId === "invoice-p2p.approval.auto_threshold") {
    const threshold = typeof proposedValue === "number" ? proposedValue : Number(proposedValue);
    for (const w of completed) {
      if (w.invoice.amount <= threshold) {
        wouldBeDifferent++;
        impactedWorkflowIds.push(w.id);
      }
    }
  }

  return {
    scopeDays: days,
    totalEvaluated: completed.length,
    wouldBeDifferent,
    impactedWorkflowIds: impactedWorkflowIds.slice(0, 20),
  };
}

export function dryRunPolicyTool(store: StateStore) {
  return defineTool("dry-run-policy", {
    description: "Simulate a policy value change against completed workflows — shows how many outcomes would have differed.",
    parameters: z.object({
      policyId: z.string().describe("The policy identifier to simulate changing"),
      proposedValue: z.unknown().describe("The new value to test for the policy"),
      scopeDays: z.number().optional().describe("Number of days of history to replay (default 30)"),
    }),
    skipPermission: true,
    handler: async (args) => dryRunPolicyImpl(store, args),
  });
}
