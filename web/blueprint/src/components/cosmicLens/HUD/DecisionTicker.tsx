import { useEffect, useRef, useState } from "react";

/** Fields shared by all ticker item kinds. */
type TickerBase = {
  id: string;
  decided_at?: string;
};

type TickerItem =
  | (TickerBase & {
      kind: "Decision";
      persona_role?: string;
      verdict?: string;
      reason?: string;
      workflow_id?: string;
      phase?: string;
      decided_on?: string[];
      attributes?: Record<string, unknown>;
    })
  | (TickerBase & {
      kind: "Insight";
      role?: string;
      scope?: string;
      headline?: string;
      fingerprint?: string;
    });

const VERDICT_LABEL: Record<string, string> = {
  approve: "approved",
  reject: "rejected",
  escalate: "escalated",
  defer: "deferred",
  freeze: "froze",
  unfreeze: "unfroze",
  cap: "capped",
};

const PERSONA_TITLE: Record<string, string> = {
  cfo: "CFO",
  ceo: "CEO",
  controller: "Controller",
  ap_clerk: "AP Clerk",
  treasurer: "Treasurer",
  hr_director: "HR Director",
  sourcing_lead: "Sourcing Lead",
};

function prettyEntity(e?: string): string {
  if (!e) return "";
  for (const p of ["BRAND-", "ORG-vendor-", "FX:", "DEPT:"]) {
    if (e.startsWith(p)) return e.slice(p.length).replace(/-/g, " ");
  }
  return e;
}

const FALLBACK_HUE = "#8a93a8";

// autonomous-domain-insights v1.1 (F1): fetch the role→hue map once on
// mount and cache it. Tiny payload (~50 entries), one HTTP call total.
function usePersonaColors(enabled: boolean): Record<string, string | null> {
  const [colors, setColors] = useState<Record<string, string | null>>({});
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    fetch("/api/personas/colors")
      .then((r) => (r.ok ? r.json() : {}))
      .then((d) => {
        if (!cancelled && d && typeof d === "object")
          setColors(d as Record<string, string | null>);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [enabled]);
  return colors;
}

function personaSpan(
  role: string | undefined,
  label: string,
  colors: Record<string, string | null>,
) {
  const hue = (role && colors[role]) || FALLBACK_HUE;
  return (
    <span style={{ color: hue }}>
      {label}
    </span>
  );
}

function renderItemNodes(
  item: TickerItem,
  colors: Record<string, string | null>,
) {
  if (item.kind === "Insight") {
    const role = item.role || "";
    const who = PERSONA_TITLE[role] || role || "?";
    return (
      <>
        {personaSpan(role, who, colors)}
        {`: ${item.headline || "(no headline)"}`}
      </>
    );
  }
  const role = item.persona_role || "";
  const who = PERSONA_TITLE[role] || role || "system";
  const verb = VERDICT_LABEL[item.verdict || ""] || item.verdict || "decided";
  const targets = (item.decided_on || [])
    .slice(0, 3)
    .map(prettyEntity)
    .filter(Boolean)
    .join(", ");
  return (
    <>
      {personaSpan(role, who, colors)}
      {` ${verb}${targets ? " " + targets : ""}`}
    </>
  );
}

function relAge(iso: string | undefined, now: number): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const sec = Math.max(0, Math.floor((now - t) / 1000));
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m`;
  return `${Math.floor(sec / 3600)}h`;
}

export function DecisionTicker({
  enabled = true,
  max = 8,
  isReplay = false,
}: {
  enabled?: boolean;
  max?: number;
  isReplay?: boolean;
}) {
  const [items, setItems] = useState<TickerItem[]>([]);
  const [now, setNow] = useState(Date.now());
  const esRef = useRef<EventSource | null>(null);
  const personaColors = usePersonaColors(enabled);

  useEffect(() => {
    if (!enabled) return;
    fetch(`/api/ticker/recent?limit=${max}`)
      .then((r) => (r.ok ? r.json() : { ticker: [] }))
      .then((d) =>
        setItems(Array.isArray(d?.ticker) ? d.ticker.slice(0, max) : []),
      )
      .catch(() => {});
  }, [enabled, max]);

  useEffect(() => {
    if (!enabled) return;
    const es = new EventSource("/api/ticker/stream");
    esRef.current = es;
    es.onmessage = (ev) => {
      try {
        const item = JSON.parse(ev.data);
        setItems((prev) => [item, ...prev].slice(0, max));
      } catch {}
    };
    es.onerror = () => {
      /* allow auto-reconnect */
    };
    return () => {
      es.close();
      esRef.current = null;
    };
  }, [enabled, max]);

  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(id);
  }, [enabled]);

  if (!enabled) return null;
  return (
    <div
      style={{
        position: "fixed",
        left: 16,
        right: 16,
        bottom: 16,
        background: "rgba(8,12,24,0.85)",
        color: "#dbe5ff",
        borderRadius: 8,
        padding: "10px 14px",
        border: "1px solid rgba(120,160,255,0.25)",
        boxShadow: "0 4px 24px rgba(0,0,0,0.6)",
        font: "12px/1.5 ui-monospace, SF Mono, monospace",
        zIndex: 50,
        maxHeight: "12vh",
        overflow: "hidden",
      }}
    >
      <div style={{ opacity: 0.6, marginBottom: 4 }}>
        {isReplay ? "Recorded" : "Live"} · org decisions and insights
      </div>
      {items.length === 0 && (
        <div style={{ opacity: 0.5 }}>(no recent activity)</div>
      )}
      {items.map((it, idx) => (
        <div
          key={it.id || idx}
          style={{
            display: "flex",
            justifyContent: "space-between",
            opacity: idx === 0 ? 1 : Math.max(0.4, 1 - idx * 0.08),
          }}
        >
          <span>{renderItemNodes(it, personaColors)}</span>
          <span style={{ opacity: 0.5, marginLeft: 12 }}>
            {relAge(it.decided_at, now)}
          </span>
        </div>
      ))}
    </div>
  );
}
