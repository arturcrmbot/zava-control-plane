import { useEffect, useRef, useState } from "react";

// autonomous-domain-insights v1.1 (H1): when a policy_set Decision lands on
// the live ticker stream, paint an expanding coloured ring across the
// constellation so the viewer SEES the policy's reach. Spec §9 polish (d).

type Ripple = { id: number; color: string; born: number; label: string };

let _nextId = 1;

const FALLBACK_HUE = "#88c4ff";
const RIPPLE_MS = 2500;
const CLEANUP_MS = 2600;

const VERDICT_PAST: Record<string, string> = {
  approve: "approved",
  reject: "rejected",
  escalate: "escalated",
  defer: "deferred",
  freeze: "froze",
  unfreeze: "unfroze",
  cap: "capped",
};

const ROLE_LABEL: Record<string, string> = {
  cfo: "CFO",
  ceo: "CEO",
  controller: "Controller",
  ap_clerk: "AP Clerk",
  treasurer: "Treasurer",
  hr_director: "HR Director",
  sourcing_lead: "Sourcing Lead",
};

function buildRippleLabel(item: any): string {
  const role = ROLE_LABEL[String(item.persona_role || "")] || String(item.persona_role || "");
  const rawVerdict = String(item.verdict || "").trim();
  const verdict = VERDICT_PAST[rawVerdict] || rawVerdict;
  const rawTarget = String((item.decided_on?.[0] ?? item.workflow_id ?? ""));
  const target = rawTarget
    .replace(/^BRAND-/, "")
    .replace(/[-_]/g, " ")
    .trim();
  if (role && verdict && target) return `${role} ${verdict} policy for ${target}`;
  if (role && verdict) return `${role} ${verdict} policy`;
  if (role) return `${role} policy update`;
  return "Policy update";
}

function usePersonaColors(enabled: boolean): Record<string, string> {
  const [colors, setColors] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    fetch("/api/personas/colors")
      .then((r) => (r.ok ? r.json() : {}))
      .then((d) => {
        if (!cancelled && d && typeof d === "object") {
          // strip nulls so lookup falls through to fallback
          const clean: Record<string, string> = {};
          for (const [k, v] of Object.entries(d)) {
            if (typeof v === "string" && v) clean[k] = v;
          }
          setColors(clean);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [enabled]);
  return colors;
}

export function PolicyRipple({ enabled = true }: { enabled?: boolean }) {
  const [ripples, setRipples] = useState<Ripple[]>([]);
  const colors = usePersonaColors(enabled);
  const colorsRef = useRef(colors);
  useEffect(() => {
    colorsRef.current = colors;
  }, [colors]);

  useEffect(() => {
    if (!enabled) return;
    const es = new EventSource("/api/ticker/stream");
    const timeouts: ReturnType<typeof setTimeout>[] = [];
    es.onmessage = (ev) => {
      try {
        const item = JSON.parse(ev.data);
        if (item.kind !== "Decision" || item.phase !== "policy_set") return;
        const role = String(item.persona_role || "");
        const color = colorsRef.current[role] || FALLBACK_HUE;
        const label = buildRippleLabel(item);
        const id = _nextId++;
        setRipples((prev) => [...prev, { id, color, born: Date.now(), label }]);
        const t = setTimeout(() => {
          setRipples((prev) => prev.filter((r) => r.id !== id));
        }, CLEANUP_MS);
        timeouts.push(t);
      } catch {
        /* swallow malformed event */
      }
    };
    es.onerror = () => {
      /* allow auto-reconnect */
    };
    return () => {
      es.close();
      for (const t of timeouts) clearTimeout(t);
    };
  }, [enabled]);

  if (!enabled) return null;
  return (
    <div
      data-testid="policy-ripple-overlay"
      style={{
        position: "fixed",
        inset: 0,
        pointerEvents: "none",
        zIndex: 40,
        overflow: "hidden",
      }}
    >
      {ripples.map((r) => (
        // 3 concentric circles with staggered animation-delay so a single
        // policy_set produces a layered "wavefront" rather than one ring.
        <div key={r.id}>
          {[0, 220, 440].map((delayMs) => (
            <div
              key={delayMs}
              data-testid="policy-ripple-ring"
              className="zava-policy-ripple"
              style={{
                position: "absolute",
                top: "50%",
                left: "50%",
                width: 0,
                height: 0,
                transform: "translate(-50%, -50%)",
                border: `2px solid ${r.color}`,
                borderRadius: "50%",
                boxShadow: `0 0 18px ${r.color}`,
                opacity: 0,
                animation: `zavaPolicyRipple ${RIPPLE_MS}ms ease-out ${delayMs}ms forwards`,
              }}
            />
          ))}
          <div
            data-testid="policy-ripple-label"
            style={{
              position: "absolute",
              top: "calc(50% - 36px)",
              left: "50%",
              transform: "translateX(-50%)",
              background: "rgba(8,12,32,0.88)",
              border: `1px solid ${r.color}55`,
              borderRadius: 999,
              color: r.color,
              fontSize: 11,
              fontWeight: 600,
              padding: "3px 12px",
              whiteSpace: "nowrap",
              pointerEvents: "none",
              animation: `zavaPolicyLabel ${RIPPLE_MS}ms ease-out 0ms forwards`,
            }}
          >
            {r.label}
          </div>
        </div>
      ))}
      <style>{`
        @keyframes zavaPolicyRipple {
          0%   { width: 8vmin;   height: 8vmin;   opacity: 0.85; }
          60%  { opacity: 0.55; }
          100% { width: 220vmin; height: 220vmin; opacity: 0; }
        }
        @keyframes zavaPolicyLabel {
          0%   { opacity: 0; transform: translate(-50%, 4px); }
          10%  { opacity: 1; transform: translate(-50%, 0); }
          75%  { opacity: 1; transform: translate(-50%, 0); }
          100% { opacity: 0; transform: translate(-50%, -4px); }
        }
      `}</style>
    </div>
  );
}

export default PolicyRipple;
