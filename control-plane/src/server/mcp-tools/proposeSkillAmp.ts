import { defineTool } from "@github/copilot-sdk";
import { z } from "zod";
import { nanoid } from "nanoid";
import type { StateStore } from "@server/services/stateStore";
import type { SkillAmplification, PolicyRef } from "@shared/types";

export function proposeSkillAmpTool(store: StateStore) {
  return defineTool("propose-skill-amplification", {
    description: "Emit a skill-amplification card for an operator — provides policy context and precedents to support decision-making.",
    parameters: z.object({
      workflowId: z.string().describe("The workflow this amplification card applies to"),
      policyContext: z
        .array(
          z.object({
            title: z.string(),
            snippet: z.string(),
            source: z.string(),
          })
        )
        .optional()
        .describe("Relevant policy references to surface to the operator"),
      precedents: z
        .array(
          z.object({
            workflowId: z.string(),
            outcome: z.string(),
            rationale: z.string(),
          })
        )
        .optional()
        .describe("Past similar decisions and their rationale"),
      recommendedApproach: z
        .string()
        .describe("Concise recommended approach for the operator"),
    }),
    skipPermission: true,
    handler: async ({ workflowId, policyContext, precedents, recommendedApproach }) => {
      const id = `AMP-${nanoid(8)}`;
      const amp: SkillAmplification = {
        id,
        workflowId,
        policyContext: (policyContext ?? []) as PolicyRef[],
        precedents: precedents ?? [],
        recommendedApproach,
        createdAt: Date.now(),
      };
      store.appendAmplification(workflowId, amp);
      return { amplificationId: id };
    },
  });
}
