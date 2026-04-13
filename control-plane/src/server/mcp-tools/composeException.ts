import { defineTool } from "@github/copilot-sdk";
import { z } from "zod";
import { nanoid } from "nanoid";
import type { StateStore } from "@server/services/stateStore";
import type { EventBus } from "@server/services/eventBus";
import type { AuditLogger } from "@server/services/auditLogger";
import type { Exception, ExceptionCategory, ExceptionOption, PolicyRef } from "@shared/types";

export function composeExceptionTool(store: StateStore, _bus: EventBus, audit: AuditLogger) {
  return defineTool("compose-exception", {
    description: "Write an exception to the queue. Non-revocable action — audited before and after write.",
    parameters: z.object({
      workflowId: z.string().describe("The workflow this exception applies to"),
      severity: z.enum(["critical", "high", "medium"]).describe("Exception severity"),
      category: z.string().describe("Exception category (e.g. po-mismatch, duplicate-invoice)"),
      summary: z.string().describe("Concise summary of the exception for the operator"),
      recommendation: z.string().describe("Agent recommendation for resolving this exception"),
      options: z
        .array(
          z.object({
            label: z.string(),
            action: z.string(),
            nonRevocable: z.boolean(),
          })
        )
        .optional()
        .describe("Decision options to present to the operator (defaults to approve/reject)"),
      relatedPolicyRefs: z
        .array(
          z.object({
            title: z.string(),
            snippet: z.string(),
            source: z.string(),
          })
        )
        .optional()
        .describe("Policy references that informed this exception"),
      bulkCandidateIds: z
        .array(z.string())
        .optional()
        .describe("Other workflow IDs that are candidates for bulk resolution"),
      confidence: z
        .number()
        .min(0)
        .max(1)
        .optional()
        .describe("Agent confidence score between 0 and 1"),
    }),
    skipPermission: true,
    handler: async ({
      workflowId,
      severity,
      category,
      summary,
      recommendation,
      options,
      relatedPolicyRefs,
      bulkCandidateIds,
      confidence,
    }) => {
      // Hook-gated non-revocable action: audit BEFORE writing
      audit.log({
        action: "compose-exception.pre",
        details: { workflowId, severity, category, summary },
        timestamp: Date.now(),
      });

      const defaultOptions: ExceptionOption[] = [
        { label: "Approve", action: "approve", nonRevocable: true },
        { label: "Reject", action: "reject", nonRevocable: false },
      ];

      const exc: Exception = {
        id: `EXC-${nanoid(8)}`,
        workflowId,
        composedBy: "fleet-manager",
        severity,
        category: category as ExceptionCategory,
        summary,
        recommendation,
        options: options ?? defaultOptions,
        relatedPolicyRefs: (relatedPolicyRefs ?? []) as PolicyRef[],
        bulkCandidateIds,
        confidence: confidence ?? 0.8,
        createdAt: Date.now(),
      };

      store.upsertException(exc);

      audit.log({
        action: "compose-exception.emitted",
        details: { exceptionId: exc.id, workflowId, severity, category },
        timestamp: Date.now(),
      });

      return { exceptionId: exc.id };
    },
  });
}
