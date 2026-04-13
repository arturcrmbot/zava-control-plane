import { defineTool } from "@github/copilot-sdk";
import { z } from "zod";
export function queryTracesTool(store) {
    return defineTool("query-traces", {
        description: "OTEL spans for a specific workflow. Optionally filter by phase name.",
        parameters: z.object({
            workflowId: z.string().describe("The workflow ID to retrieve spans for"),
            phase: z.string().optional().describe("Filter spans to only those belonging to this phase"),
        }),
        skipPermission: true,
        handler: async ({ workflowId, phase }) => {
            let spans = store.getSpans(workflowId);
            if (phase) {
                spans = spans.filter(s => s.attributes["workflow.phase"] === phase);
            }
            return {
                workflowId,
                spanCount: spans.length,
                spans: spans.map(s => ({
                    spanId: s.spanId,
                    parentSpanId: s.parentSpanId,
                    name: s.name,
                    phase: s.attributes["workflow.phase"],
                    durationMs: s.endMs - s.startMs,
                    status: s.status,
                    tool: s.attributes["tool.name"],
                    model: s.attributes["llm.model"],
                    tokensIn: s.attributes["llm.tokens.in"],
                    tokensOut: s.attributes["llm.tokens.out"],
                    costUsd: s.attributes["cost.usd"],
                })),
            };
        },
    });
}
