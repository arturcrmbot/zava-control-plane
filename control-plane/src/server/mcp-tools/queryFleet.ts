import { defineTool } from "@github/copilot-sdk";
import { z } from "zod";
import type { StateStore, WorkflowFilters } from "@server/services/stateStore";
import type { PhaseName } from "@shared/types";

export function queryFleetTool(store: StateStore) {
  return defineTool("query-fleet", {
    description: "Aggregated fleet state — returns workflow counts by phase/status and recent open exceptions.",
    parameters: z.object({
      phase: z.string().optional().describe("Filter by current phase name"),
      agency: z.string().optional().describe("Filter by agency name"),
      hasException: z.boolean().optional().describe("Filter to workflows that have an active exception"),
    }),
    skipPermission: true,
    handler: async ({ phase, agency, hasException }) => {
      const filters: WorkflowFilters = {
        phase: phase as PhaseName | undefined,
        agency,
        hasException,
      };
      const workflows = store.listWorkflows(filters);
      const allExceptions = store.listExceptions();

      const byPhase: Record<string, number> = {};
      const byStatus: Record<string, number> = {};
      for (const w of workflows) {
        byPhase[w.currentPhase] = (byPhase[w.currentPhase] ?? 0) + 1;
        byStatus[w.status] = (byStatus[w.status] ?? 0) + 1;
      }

      const recentExceptions = allExceptions
        .sort((a, b) => b.createdAt - a.createdAt)
        .slice(0, 5)
        .map(e => ({
          id: e.id,
          workflowId: e.workflowId,
          severity: e.severity,
          category: e.category,
          summary: e.summary,
          confidence: e.confidence,
        }));

      return {
        total: workflows.length,
        byPhase,
        byStatus,
        openExceptionCount: allExceptions.length,
        recentExceptions,
      };
    },
  });
}
