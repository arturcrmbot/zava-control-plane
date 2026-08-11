/**
 * Narrator — invisible-by-default cinematic overlay for the full Aurora demo
 * arc. When triggered (via `triggerNarrator(arcResponse)`) it sequences one
 * centered text bubble per phase from `/api/demo/trigger/full-aurora-arc`,
 * each visible for ~2.5s, fading in/out smoothly above the DecisionTicker.
 *
 * Purely additive: when not triggered, renders nothing.
 */

import { useEffect, useState } from "react";

type Phase = {
  phase: string;
  elapsed_ms: number;
  headline?: string;
  summary?: unknown;
  freezes_remaining?: number;
  cascades?: unknown[];
  policy_workflow_id?: string;
};

export type ArcResult = {
  phases: Phase[];
  total_elapsed_ms: number;
  narrative: string;
};

const PHASE_LINES: Record<
  string,
  (p: Phase) => { primary: string; secondary?: string }
> = {
  overrun: () => ({
    primary: "A budget overrun arrived on Aurora.",
    secondary:
      "The overrun landed on Aurora and begins a response across finance, operations, and executive oversight.",
  }),
  cfo_observe: (p) => ({
    primary: "CFO agent observes within delegated authority.",
    secondary: p.headline || "",
  }),
  approve: () => ({
    primary: "Operator approves.",
    secondary:
      "One click. The freeze becomes graph-resident policy in milliseconds.",
  }),
  cfo_observe_post: (p) => ({
    primary: "CFO already knows.",
    secondary: `Aurora dropped from the proposal list — ${
      p.freezes_remaining ?? "?"
    } freeze(s) remaining. The system noticed itself.`,
  }),
  spawn_invoices: (p) => ({
    primary: "In-flight work auto-escalates.",
    secondary: `${
      (p.cascades || []).length
    } new ap-invoices on Aurora — every one auto-escalated up the chain because the freeze is live.`,
  }),
  ceo_synthesise: (p) => ({
    primary: "CEO synthesises across the org.",
    secondary: p.headline || "",
  }),
};

const PER_BUBBLE_MS = 2500;

let _trigger: ((arc: ArcResult) => void) | null = null;
export function triggerNarrator(arc: ArcResult) {
  if (_trigger) _trigger(arc);
}

export function Narrator() {
  const [arc, setArc] = useState<ArcResult | null>(null);
  const [idx, setIdx] = useState(-1);

  useEffect(() => {
    _trigger = (a: ArcResult) => {
      setArc(a);
      setIdx(0);
    };
    return () => {
      _trigger = null;
    };
  }, []);

  useEffect(() => {
    if (!arc || idx < 0) return;
    if (idx >= arc.phases.length) {
      const t = setTimeout(() => {
        setArc(null);
        setIdx(-1);
      }, 800);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setIdx(idx + 1), PER_BUBBLE_MS);
    return () => clearTimeout(t);
  }, [arc, idx]);

  if (!arc || idx < 0 || idx >= arc.phases.length) return null;
  const phase = arc.phases[idx];
  const renderer =
    PHASE_LINES[phase.phase] ||
    ((p: Phase) => ({ primary: p.phase, secondary: "" }));
  const { primary, secondary } = renderer(phase);

  return (
    <div
      data-testid="narrator-bubble"
      style={{
        position: "fixed",
        left: "50%",
        bottom: "16vh",
        transform: "translateX(-50%)",
        zIndex: 70,
        maxWidth: "min(640px, 80vw)",
        textAlign: "center",
        pointerEvents: "none",
        animation: "narrationFadeIn 0.4s ease-out",
      }}
    >
      <div
        style={{
          background: "rgba(8,12,24,0.94)",
          border: "1px solid rgba(255,243,184,0.4)",
          borderRadius: 14,
          padding: "16px 22px",
          font: "13px/1.5 ui-monospace, SF Mono, monospace",
          color: "#fff3b8",
          boxShadow:
            "0 12px 48px rgba(0,0,0,0.7), 0 0 32px rgba(255,243,184,0.18)",
        }}
      >
        <div
          style={{
            fontSize: 10,
            opacity: 0.6,
            letterSpacing: 1.5,
            textTransform: "uppercase",
            marginBottom: 6,
          }}
        >
          {idx + 1} / {arc.phases.length} · {phase.phase}
        </div>
        <div
          style={{
            fontSize: 18,
            fontWeight: 600,
            marginBottom: 8,
            color: "#fff3b8",
          }}
        >
          {primary}
        </div>
        {secondary && (
          <div style={{ fontSize: 13, opacity: 0.85, color: "#dbe5ff" }}>
            {secondary}
          </div>
        )}
      </div>
      <style>{`
        @keyframes narrationFadeIn {
          from { opacity: 0; transform: translate(-50%, 12px); }
          to   { opacity: 1; transform: translate(-50%, 0); }
        }
      `}</style>
    </div>
  );
}
