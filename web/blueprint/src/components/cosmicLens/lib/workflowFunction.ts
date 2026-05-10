/**
 * Cosmic Lens v2 — Workflow → Function resolver.
 *
 * Workflow.function is sometimes "legacy" (for older durable functions like
 * hiring) so we map workflow_type → owning function via /api/functions
 * ownsDomains list.
 */

import type { FunctionMeta, WorkflowMoonData } from "./types";

export function buildWorkflowTypeToFunction(functions: FunctionMeta[]): Map<string, string> {
  const map = new Map<string, string>();
  for (const fn of functions) {
    const fnKey = fn.name ?? fn.key;
    if (!fnKey) continue;
    const domains = fn.ownsDomains ?? fn.domains ?? [];
    for (const d of domains) {
      map.set(d, fnKey);
    }
  }
  return map;
}

/** Resolve a workflow's owning function key.
 *  Priority: explicit wf.function (when not "legacy") → wf.workflow_type → "ops" fallback. */
export function resolveFunction(
  wf: WorkflowMoonData,
  wfTypeMap: Map<string, string>,
): string {
  const fn = wf.function;
  if (fn && fn !== "legacy" && fn !== "unknown") return fn;
  const byType = wf.workflow_type ? wfTypeMap.get(wf.workflow_type) : undefined;
  if (byType) return byType;
  return "ops";
}

/** Quick prefix table for the canonical fleet workflow ids. Last-resort guess. */
export const PREFIX_TO_WORKFLOW_TYPE: Record<string, string> = {
  VKY: "vendor-kyc",
  API: "ap-invoice",
  PRR: "perf-review",
  HIRE: "hiring",
  TFX: "treasury-fx",
  CC: "creative-campaign",
  CR: "contract-renewal",
  PO: "purchase-order",
  CRV: "contract-review",
  DPIA: "privacy-dpia",
  L2C: "lead-to-cash",
  ITA: "it-access-request",
  EO: "employee-onboarding",
  TPA: "travel-preapproval",
  HTP: "hire-to-productive",
  FYC: "fy-close",
  BP: "board-prep",
};

export function workflowTypeFromId(id: string): string | undefined {
  const prefix = id.split("-")[0];
  return PREFIX_TO_WORKFLOW_TYPE[prefix];
}
