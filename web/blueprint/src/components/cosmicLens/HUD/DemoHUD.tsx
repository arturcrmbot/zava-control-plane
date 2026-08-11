/**
 * DemoHUD — operator-only floating overlay on the constellation page that
 * one-click triggers the v1.1 demo scenarios (Aurora overrun, brand overrun,
 * in-flight invoice burst). Anchored top-right, offset down so it never
 * collides with the right-edge WorkflowDrawer when both are open.
 *
 * Visible only when the parent passes `enabled={true}` — gated in
 * ConstellationPage by `?demo=1`. Default: hidden.
 */

import { useState } from "react";
import { triggerNarrator } from "./Narrator";

type Scenario = {
  id: string;
  title: string;
  description: string;
  trigger: () => Promise<Response>;
};

const SCENARIOS: Scenario[] = [
  {
    id: "full-aurora-arc",
    title: "🎬 Full Aurora Demo Arc",
    description:
      "One-click: overrun → CFO observation → auto-approve → cascade → CEO synthesis. Watch the ticker.",
    trigger: () =>
      fetch(
        "/api/demo/trigger/full-aurora-arc?delay_seconds=2.0&count=3",
        { method: "POST" },
      ),
  },
  {
    id: "aurora-overrun",
    title: "Aurora Budget Overrun",
    description:
      "Push BRAND-aurora spend above 95% of FY budget + spawn 3 in-flight ap-invoices on Aurora. CFO will recommend a freeze on the next cadence tick.",
    trigger: () =>
      fetch("/api/demo/trigger/aurora-overrun", { method: "POST" }),
  },
  {
    id: "in-flight-only",
    title: "Aurora In-Flight Invoices",
    description:
      "Spawn 3 ap-invoices on Aurora WITHOUT injecting overrun. If CFO has already proposed a freeze, watch the new invoices auto-escalate.",
    trigger: () =>
      fetch(
        "/api/demo/trigger/in-flight-invoices?brand_id=BRAND-aurora&count=3",
        { method: "POST" },
      ),
  },
  {
    id: "solace-overrun",
    title: "Solace Budget Overrun",
    description:
      "Push BRAND-solace above 95% (already over today; this tops it up) and spawn 2 invoices to drive the freeze recommendation on the alt brand.",
    trigger: async () => {
      await fetch(
        "/api/demo/trigger/brand-overrun?brand_id=BRAND-solace&target_pct=0.95",
        { method: "POST" },
      );
      return fetch(
        "/api/demo/trigger/in-flight-invoices?brand_id=BRAND-solace&count=2",
        { method: "POST" },
      );
    },
  },
  {
    id: "ember-overrun",
    title: "Ember Budget Overrun",
    description:
      "Generic any-brand trigger: push BRAND-ember to 95% of FY budget. Useful for showing the freeze logic generalises beyond Aurora/Solace.",
    trigger: () =>
      fetch(
        "/api/demo/trigger/brand-overrun?brand_id=BRAND-ember&target_pct=0.95",
        { method: "POST" },
      ),
  },
  {
    id: "fx-exposure",
    title: "Treasury FX Exposure Spike",
    description:
      "Insert 5 fresh treasury-fx approvals on EUR/GBP totalling £10.8M of notional. Treasurer will recommend a hedging cap on the next cadence tick.",
    trigger: () =>
      fetch("/api/demo/trigger/fx-exposure", { method: "POST" }),
  },
  {
    id: "vendor-concentration",
    title: "Vendor Concentration Risk",
    description:
      "Insert ~50 PO rows on the largest vendor to push concentration above 12% of total vendor spend. Sourcing Lead will propose a vendor pause.",
    trigger: () =>
      fetch("/api/demo/trigger/vendor-concentration", { method: "POST" }),
  },
  {
    id: "department-attrition",
    title: "Department Attrition Burst",
    description:
      "Mark ~30% of currently-employed Tech Persons as leavers within the last 30 days. HR Director will surface the spike on the next cadence tick.",
    trigger: () =>
      fetch(
        "/api/demo/trigger/department-attrition?department=Tech",
        { method: "POST" },
      ),
  },
  {
    id: "reset-demo-state",
    title: "🧹 Reset Demo State",
    description:
      "Wipes demo-added Money / Workflows / Decisions / Insights. The cadence loop will re-publish baseline insights within 15 seconds.",
    trigger: () =>
      fetch("/api/demo/trigger/reset?keep_seed=true", { method: "POST" }),
  },
];

const PANEL_BG = "linear-gradient(to bottom, rgb(2,6,23), rgb(15,23,42))";
const BORDER = "1px solid rgba(99,102,241,0.3)";
const MUTED = "rgba(148,163,184,0.85)";

export function DemoHUD({ enabled }: { enabled: boolean }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{
    id: string;
    ok: boolean;
    msg: string;
  } | null>(null);

  if (!enabled) return null;

  const onTrigger = async (s: Scenario) => {
    setBusy(s.id);
    setFeedback(null);
    try {
      const r = await s.trigger();
      const body = await r.json().catch(() => ({}));
      if (
        r.ok &&
        s.id === "full-aurora-arc" &&
        body &&
        Array.isArray((body as { phases?: unknown }).phases)
      ) {
        triggerNarrator(body as Parameters<typeof triggerNarrator>[0]);
      }
      setFeedback({
        id: s.id,
        ok: r.ok,
        msg: r.ok
          ? `Triggered. ${JSON.stringify(body).slice(0, 200)}`
          : `Failed (${r.status})`,
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setFeedback({ id: s.id, ok: false, msg });
    } finally {
      setBusy(null);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        style={{
          position: "absolute",
          top: 72,
          left: 16,
          zIndex: 35,
          background: PANEL_BG,
          border: BORDER,
          color: "#e2e8f0",
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
          fontSize: 11,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          padding: "8px 12px",
          borderRadius: 6,
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: 8,
          boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
        }}
        aria-label="Open demo controls"
      >
        <span
          style={{
            display: "inline-block",
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: "rgb(34,197,94)",
            boxShadow: "0 0 8px rgb(34,197,94)",
            animation: "demoHudPulse 1.6s ease-in-out infinite",
          }}
        />
        Demo Controls
        <style>{`
          @keyframes demoHudPulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.45; transform: scale(0.8); }
          }
        `}</style>
      </button>
    );
  }

  return (
    <div
      style={{
        position: "absolute",
        top: 72,
        left: 16,
        zIndex: 35,
        width: 360,
        maxHeight: "calc(100vh - 32px)",
        overflowY: "auto",
        background: PANEL_BG,
        border: BORDER,
        borderRadius: 8,
        color: "#e2e8f0",
        fontFamily: "ui-sans-serif, system-ui",
        fontSize: 12,
        boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 12px",
          borderBottom: "1px solid rgba(99,102,241,0.2)",
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
          fontSize: 11,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: MUTED,
        }}
      >
        <span>Demo Controls</span>
        <button
          type="button"
          onClick={() => setOpen(false)}
          style={{
            background: "transparent",
            border: "none",
            color: MUTED,
            cursor: "pointer",
            fontSize: 14,
            lineHeight: 1,
            padding: 0,
          }}
          aria-label="Close demo controls"
        >
          ×
        </button>
      </div>
      <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
        {SCENARIOS.map((s) => {
          const isBusy = busy === s.id;
          const fb = feedback?.id === s.id ? feedback : null;
          return (
            <div
              key={s.id}
              style={{
                background: "rgba(15,23,42,0.6)",
                border: "1px solid rgba(99,102,241,0.18)",
                borderRadius: 6,
                padding: 10,
              }}
            >
              <div
                style={{
                  fontFamily:
                    "ui-monospace, SFMono-Regular, Menlo, monospace",
                  fontSize: 12,
                  color: "#e2e8f0",
                  marginBottom: 4,
                }}
              >
                {s.title}
              </div>
              <div
                style={{
                  color: MUTED,
                  lineHeight: 1.4,
                  marginBottom: 8,
                }}
              >
                {s.description}
              </div>
              <button
                type="button"
                onClick={() => onTrigger(s)}
                disabled={busy !== null}
                style={{
                  background: isBusy
                    ? "rgba(99,102,241,0.2)"
                    : "rgba(99,102,241,0.35)",
                  border: "1px solid rgba(99,102,241,0.6)",
                  color: "#e2e8f0",
                  fontFamily:
                    "ui-monospace, SFMono-Regular, Menlo, monospace",
                  fontSize: 11,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  padding: "5px 10px",
                  borderRadius: 4,
                  cursor: busy !== null ? "not-allowed" : "pointer",
                  opacity: busy !== null && !isBusy ? 0.5 : 1,
                }}
              >
                {isBusy ? "Triggering…" : "Trigger"}
              </button>
              {fb && (
                <div
                  style={{
                    marginTop: 8,
                    fontSize: 11,
                    color: fb.ok ? "rgb(134,239,172)" : "rgb(252,165,165)",
                    fontFamily:
                      "ui-monospace, SFMono-Regular, Menlo, monospace",
                    wordBreak: "break-word",
                  }}
                >
                  {fb.msg}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
