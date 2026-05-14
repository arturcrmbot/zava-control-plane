import { useEffect, useRef, useState } from "react";
import type { PulseSnapshot, CosmicFlash } from "../lib/types";
import { colorForEntityType } from "../lib/colors";
import { pluralize } from "../../../../../shared/humanize";

interface KnowledgePulseProps {
  pulse: PulseSnapshot | null;
  flashesRef: React.MutableRefObject<{ buffer: CosmicFlash[]; version: number }>;
  onOpenEntity: (id: string) => void;
}

const SPARK_LEN = 60;

export function KnowledgePulse({ pulse, flashesRef, onOpenEntity }: KnowledgePulseProps) {
  const decisionSpark = useRef<number[]>(new Array(SPARK_LEN).fill(0));
  const linksSpark = useRef<number[]>(new Array(SPARK_LEN).fill(0));
  const [, force] = useState(0);

  useEffect(() => {
    let lastVersion = 0;
    let dec = 0, lnk = 0;
    const tick = setInterval(() => {
      const ref = flashesRef.current;
      if (ref.version !== lastVersion) {
        const newCount = Math.max(1, Math.min(ref.buffer.length, ref.version - lastVersion));
        const tail = ref.buffer.slice(ref.buffer.length - newCount);
        for (const f of tail) {
          if (f.type === "decision.recorded") dec++;
          if (f.type === "entity.linked") lnk++;
        }
        lastVersion = ref.version;
      }
      decisionSpark.current = [...decisionSpark.current.slice(1), dec];
      linksSpark.current = [...linksSpark.current.slice(1), lnk];
      dec = 0; lnk = 0;
      force(t => t + 1);
    }, 1000);
    return () => clearInterval(tick);
  }, [flashesRef]);

  return (
    <div style={{
      position: "absolute", top: 56, left: 16, right: 16,
      display: "flex", gap: 16,
      pointerEvents: "auto", zIndex: 25,
    }}>
      <Stat title="Total records" value={pulse?.total ?? "—"} sub={pulse && pulse.growth_60s > 0 ? `+${pulse.growth_60s} in last 60s` : "no growth"} />
      <Stat title="Decisions/min" value={pulse?.decisions_per_min?.toFixed(1) ?? "—"} sparkline={decisionSpark.current} color="#fbbf24" />
      <Stat title="Links/min" value={pulse?.links_per_min?.toFixed(1) ?? "—"} sparkline={linksSpark.current} color="#a78bfa" />
      <CrossDomainPanel cross={pulse?.cross_domain_top ?? []} onOpenEntity={onOpenEntity} />
    </div>
  );
}

function Stat({
  title, value, sub, sparkline, color,
}: {
  title: string; value: number | string; sub?: string;
  sparkline?: number[]; color?: string;
}) {
  return (
    <div style={{
      flex: 1, minWidth: 140,
      background: "rgba(2,6,23,0.7)", border: "1px solid rgba(99,102,241,0.18)",
      padding: "8px 12px", color: "#e2e8f0",
      fontFamily: "ui-sans-serif, system-ui",
    }}>
      <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: 0.8, color: "#64748b" }}>{title}</div>
      <div style={{ fontSize: 18, fontWeight: 700, marginTop: 2 }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2 }}>{sub}</div>}
      {sparkline && <Sparkline values={sparkline} color={color ?? "#22d3ee"} />}
    </div>
  );
}

function Sparkline({ values, color }: { values: number[]; color: string }) {
  const max = Math.max(1, ...values);
  const w = 120, h = 18;
  const step = w / Math.max(1, values.length - 1);
  const pts = values.map((v, i) => `${(i * step).toFixed(1)},${(h - (v / max) * h).toFixed(1)}`).join(" ");
  return (
    <svg width={w} height={h} style={{ display: "block", marginTop: 4 }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.4} opacity={0.85} />
    </svg>
  );
}

function CrossDomainPanel({
  cross, onOpenEntity,
}: { cross: PulseSnapshot["cross_domain_top"]; onOpenEntity: (id: string) => void }) {
  return (
    <div style={{
      flex: 2, minWidth: 220,
      background: "rgba(2,6,23,0.7)", border: "1px solid rgba(99,102,241,0.18)",
      padding: "8px 12px", color: "#e2e8f0",
      fontFamily: "ui-sans-serif, system-ui",
    }}>
      <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: 0.8, color: "#64748b" }}>Records that span several teams</div>
      {cross.length === 0 && <div style={{ color: "#475569", fontStyle: "italic", fontSize: 10, marginTop: 4 }}>nothing crosses domains yet</div>}
      {cross.slice(0, 3).map((e) => (
        <button
          key={e.id}
          onClick={() => onOpenEntity(e.id)}
          style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            width: "100%", marginTop: 4, padding: "3px 6px",
            background: "transparent", border: "1px solid rgba(99,102,241,0.15)",
            cursor: "pointer", color: "#e2e8f0", fontSize: 11, textAlign: "left",
            fontFamily: "inherit",
          }}
        >
          <span style={{ color: colorForEntityType(e.kind) }}>{e.id}</span>
          <span style={{ color: "#94a3b8", fontSize: 10 }}>
            {pluralize(e.workflow_types_count, "domain")} · {pluralize(e.workflow_count, "workflow")}
          </span>
        </button>
      ))}
    </div>
  );
}
