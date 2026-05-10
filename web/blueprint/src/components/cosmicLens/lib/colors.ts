/**
 * Cosmic Lens v2 — Color palette helpers.
 *
 * 5-band Capabilities palette (cool for machines, warm for humans):
 *   mcp        → cyan
 *   skill      → violet
 *   python     → teal
 *   validator  → amber
 *   persona    → warm gold/coral (HITL — distinct from all machines)
 *
 * Entities palette: by ownership domain family (Phase D).
 *
 * Function-family palette: for FunctionPlanets (Phase A).
 */

export type CityKind =
  | "mcp"
  | "skill"
  | "python"
  | "validator"
  | "persona"
  | "entity_type"
  | "unknown";

const CAPABILITY_COLORS: Record<CityKind, string> = {
  mcp: "#22d3ee", // cyan
  skill: "#a78bfa", // violet
  python: "#2dd4bf", // teal
  validator: "#fbbf24", // amber
  persona: "#fb923c", // warm coral
  entity_type: "#94a3b8", // slate (placeholder; Entities mode uses domainFor)
  unknown: "#64748b",
};

export function colorForKind(kind: string | undefined): string {
  if (!kind) return CAPABILITY_COLORS.unknown;
  const k = kind.toLowerCase() as CityKind;
  return CAPABILITY_COLORS[k] ?? CAPABILITY_COLORS.unknown;
}

/** Function-family colors for planets. */
const FUNCTION_FAMILY_COLORS: Record<string, string> = {
  finance: "#3b82f6", // blue
  hr: "#f59e0b", // amber
  legal: "#8b5cf6", // purple
  creative: "#ec4899", // magenta
  treasury: "#10b981", // emerald
  ops: "#06b6d4", // cyan
  engineering: "#14b8a6", // teal
  customer: "#f97316", // orange
  default: "#94a3b8",
};

/** Map function key → family. Conservative — extend as functions are added. */
export function familyForFunction(fn: string | undefined): string {
  if (!fn) return "default";
  const f = fn.toLowerCase();
  if (f.includes("finance") || f.includes("ap-") || f.includes("treasury") || f.includes("vendor"))
    return "finance";
  if (f.includes("hire") || f.includes("hiring") || f.includes("perf") || f.includes("hr") || f.includes("recruit"))
    return "hr";
  if (f.includes("legal") || f.includes("contract") || f.includes("compliance"))
    return "legal";
  if (f.includes("creative") || f.includes("campaign") || f.includes("marketing"))
    return "creative";
  if (f.includes("treasury") || f.includes("fx")) return "treasury";
  if (f.includes("eng") || f.includes("infra")) return "engineering";
  if (f.includes("customer") || f.includes("support")) return "customer";
  return "ops";
}

export function colorForFunction(fn: string | undefined): string {
  return FUNCTION_FAMILY_COLORS[familyForFunction(fn)] ?? FUNCTION_FAMILY_COLORS.default;
}

/** Entity-type palette (Phase D). Subset of well-known kinds → distinct hues. */
const ENTITY_TYPE_COLORS: Record<string, string> = {
  Vendor: "#3b82f6",
  Invoice: "#10b981",
  Payment: "#0ea5e9",
  Account: "#6366f1",
  Candidate: "#f97316",
  Job: "#ef4444",
  Offer: "#f59e0b",
  Contract: "#8b5cf6",
  Decision: "#fbbf24",
  Document: "#a78bfa",
  Person: "#fb923c",
  PerformanceReview: "#ec4899",
  Money: "#22c55e",
  Period: "#64748b",
};

export function colorForEntityType(kind: string): string {
  return ENTITY_TYPE_COLORS[kind] ?? "#94a3b8";
}
