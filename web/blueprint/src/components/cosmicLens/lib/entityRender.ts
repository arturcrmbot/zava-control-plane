/** Kind-specific key-attr selection + verdict colour + entity-id ref detection. */

export function keyAttrFor(kind: string, row: Record<string, unknown>): string {
  const get = (k: string) => {
    const v = row[k];
    return v === null || v === undefined ? "" : String(v);
  };
  switch (kind) {
    case "Person":
      return get("name") || get("role") || "(unnamed)";
    case "Organisation": {
      const name = get("name");
      const risk = get("risk_band");
      return risk ? `${name} · ${risk}` : name || "(unnamed)";
    }
    case "Asset":
      return [get("kind"), get("identifier")].filter(Boolean).join(" · ") || "(unnamed)";
    case "Money": {
      const amt = get("amount");
      const cur = get("currency");
      const k = get("kind");
      const head = amt && cur ? `${cur} ${amt}` : "";
      return [head, k].filter(Boolean).join(" · ") || "(no amount)";
    }
    case "Decision": {
      const verdict = get("verdict");
      const reason = get("reason").slice(0, 60);
      return reason ? `${verdict}: ${reason}` : verdict || "(no verdict)";
    }
    case "Period":
      return [get("label"), get("kind")].filter(Boolean).join(" · ") || "(unlabelled)";
    case "Place":
      return [get("name"), get("kind")].filter(Boolean).join(" · ") || "(unnamed)";
    case "Workflow":
      return [get("workflow_type"), get("status")].filter(Boolean).join(" · ");
    default:
      return get("id");
  }
}

export function verdictColor(verdict: string | undefined): string {
  switch ((verdict || "").toLowerCase()) {
    case "approve":
    case "approved":
    case "ok":
      return "#4ade80";
    case "reject":
    case "rejected":
    case "deny":
      return "#ef4444";
    case "escalate":
    case "escalated":
      return "#fbbf24";
    default:
      return "#94a3b8";
  }
}

const _ID_PATTERN = /^[A-Z][A-Z0-9_]*-[A-Za-z0-9_-]+$/;

export function extractEntityIdRefs(value: unknown): string[] {
  if (typeof value !== "string") return [];
  if (_ID_PATTERN.test(value)) return [value];
  return [];
}

export function formatRelative(targetMs: number, nowMs: number = Date.now()): string {
  const diff = Math.max(0, nowMs - targetMs);
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export function parseTimestamp(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  if (typeof v === "number") return v > 1e12 ? v : v * 1000;
  if (typeof v === "string") {
    const n = Date.parse(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}
