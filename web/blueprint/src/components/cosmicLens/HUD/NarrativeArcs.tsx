import { useEffect, useState } from "react";
import { CollapsibleHUDShell } from "./CollapsibleHUDShell";

interface NarrativeArc {
  employee_id: string;
  name: string;
  role: string;
  photo_url: string;
  one_liner: string;
  arc: string;
  function: string;
}

interface NarrativeArcsProps {
  /** Optional preloaded arcs — primarily used by tests to avoid network. */
  initialArcs?: NarrativeArc[];
  /** Fetch URL override — primarily used by tests. */
  fetchUrl?: string;
}

const FUNCTION_TINT: Record<string, string> = {
  finance: "#22d3ee",
  hr: "#a78bfa",
  legal: "#f472b6",
  procurement: "#fbbf24",
  it: "#34d399",
  commercial: "#fb7185",
};

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0] ?? "").join("").toUpperCase() || "??";
}

function tintFor(fn: string): string {
  return FUNCTION_TINT[fn] ?? "#94a3b8";
}

/**
 * Pitch D5: named-individuals HUD panel.
 *
 * Renders a stacked deck of 5–8 hand-curated humans (photo + name +
 * role + one-liner) so the cosmic lens tells a *named* story instead
 * of a role-id story. Photos are CSS-only initials avatars today;
 * real photos can drop into `/assets/personae/` later without code
 * changes.
 */
export function NarrativeArcs({ initialArcs, fetchUrl }: NarrativeArcsProps = {}) {
  const [arcs, setArcs] = useState<NarrativeArc[]>(initialArcs ?? []);
  const [open, setOpen] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialArcs) return;
    let cancelled = false;
    fetch(fetchUrl ?? "/api/personas/narrative-arcs")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: NarrativeArc[]) => {
        if (!cancelled) setArcs(data);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [initialArcs, fetchUrl]);

  return (
    <CollapsibleHUDShell
      id="narrative-arcs"
      title="Cast"
      badge={`${arcs.length}`}
      anchor="top-right"
      width={300}
      defaultCollapsed
    >
      <div data-testid="narrative-arcs">
        {error && (
          <div style={{ color: "#fca5a5", padding: 6 }}>
            could not load cast: {error}
          </div>
        )}
        {!error && arcs.length === 0 && (
          <div style={{ color: "#64748b", padding: 6 }}>loading cast…</div>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {arcs.map((a) => (
            <ArcCard key={a.employee_id} arc={a} />
          ))}
        </div>
      </div>
    </CollapsibleHUDShell>
  );
}

function ArcCard({ arc }: { arc: NarrativeArc }) {
  const tint = tintFor(arc.function);
  return (
    <div
      data-testid={`narrative-arc-${arc.employee_id}`}
      style={{
        display: "flex",
        gap: 10,
        padding: 8,
        background: "rgba(2,6,23,0.78)",
        border: `1px solid ${tint}33`,
        borderLeft: `3px solid ${tint}`,
        borderRadius: 6,
      }}
    >
      <div
        aria-hidden
        style={{
          flex: "0 0 auto",
          width: 36,
          height: 36,
          borderRadius: "50%",
          background: `linear-gradient(135deg, ${tint}55, ${tint}22)`,
          color: "#f8fafc",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontWeight: 600,
          fontSize: 13,
          letterSpacing: 0.5,
        }}
      >
        {initialsOf(arc.name)}
      </div>
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontWeight: 600,
            color: "#f1f5f9",
            display: "flex",
            justifyContent: "space-between",
            gap: 6,
          }}
        >
          <span>{arc.name}</span>
          <span style={{ color: tint, fontWeight: 500, fontSize: 11 }}>
            {arc.role}
          </span>
        </div>
        <div
          style={{
            color: "#94a3b8",
            fontSize: 11,
            marginTop: 2,
            lineHeight: 1.35,
          }}
        >
          {arc.one_liner}
        </div>
      </div>
    </div>
  );
}

export default NarrativeArcs;
