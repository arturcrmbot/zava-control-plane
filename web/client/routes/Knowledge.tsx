//
// Knowledge — the entity-graph plane as a live force-directed graph.
//
// Layout: kind tiles (filter) + heatmap on top, force graph hero panel,
// click-through detail panel with the entity's audit timeline.
//
// Data sources:
//   * /api/entities/_graph?limit=400[&kind=…]  — nodes + edges snapshot
//   * /api/entities/_kinds                      — per-kind counts + link counts
//   * /api/entities/{id}                        — payload on click
//   * /api/entities/{id}/timeline               — audit ribbon on click
//
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Network, RefreshCw, X } from "lucide-react";
import ForceGraph2D, { type ForceGraphMethods } from "react-force-graph-2d";

const KINDS = [
  "Person", "Organisation", "Asset", "Money", "Decision", "Place", "Period",
  "Workflow", "Brand", "Campaign", "Pitch", "MediaPlan", "Subsidiary",
  "Account", "CostCentre", "Insight",
] as const;
type Kind = (typeof KINDS)[number];

// Palette per kind — saturated mid-tones that read on light + dark.
const KIND_COLOR: Record<string, string> = {
  Person: "#3b82f6",
  Organisation: "#8b5cf6",
  Subsidiary: "#a78bfa",
  Asset: "#f59e0b",
  Money: "#10b981",
  Account: "#14b8a6",
  CostCentre: "#06b6d4",
  Decision: "#ef4444",
  Place: "#64748b",
  Period: "#94a3b8",
  Workflow: "#f97316",
  Brand: "#ec4899",
  Campaign: "#d946ef",
  Pitch: "#e11d48",
  MediaPlan: "#0ea5e9",
  Insight: "#eab308",
};
const DEFAULT_COLOR = "#9ca3af";
const colorForKind = (k?: string) => (k && KIND_COLOR[k]) || DEFAULT_COLOR;

type GraphNode = {
  id: string;
  kind: string;
  x?: number; y?: number; vx?: number; vy?: number;
  __degree?: number;
};
type GraphLink = { source: string | GraphNode; target: string | GraphNode; rel: string };
type GraphPayload = {
  nodes: { id: string; kind: string }[];
  edges: { src: string; dst: string; rel: string }[];
};
type KindsSummary = {
  kinds: { kind: string; count: number; sample_ids: string[]; recent_link_count: number }[];
};
type EntityPayload = Record<string, unknown> & { id?: string; _label?: string; name?: string };
type TimelineRow = { timestamp?: number; action?: string; summary?: string };

export default function Knowledge() {
  const [graph, setGraph] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>({ nodes: [], links: [] });
  const [graphError, setGraphError] = useState<string | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [kindFilter, setKindFilter] = useState<Kind | null>(null);
  const [kindsSummary, setKindsSummary] = useState<KindsSummary | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedPayload, setSelectedPayload] = useState<EntityPayload | null>(null);
  const [selectedTimeline, setSelectedTimeline] = useState<TimelineRow[]>([]);
  const [hoverId, setHoverId] = useState<string | null>(null);

  const fgRef = useRef<ForceGraphMethods | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ w: 800, h: 560 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        const r = e.contentRect;
        setSize({ w: Math.max(320, Math.floor(r.width)), h: Math.max(320, Math.floor(r.height)) });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    setGraphLoading(true);
    const qs = new URLSearchParams({ limit: "400" });
    if (kindFilter) qs.set("kind", kindFilter);
    fetch(`/api/entities/_graph?${qs.toString()}`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((d: GraphPayload) => {
        if (cancelled) return;
        const nodes: GraphNode[] = (d.nodes ?? []).map((n) => ({ id: n.id, kind: n.kind }));
        const degree: Record<string, number> = {};
        const links: GraphLink[] = (d.edges ?? []).map((e) => {
          degree[e.src] = (degree[e.src] ?? 0) + 1;
          degree[e.dst] = (degree[e.dst] ?? 0) + 1;
          return { source: e.src, target: e.dst, rel: e.rel };
        });
        for (const n of nodes) n.__degree = degree[n.id] ?? 0;
        setGraph({ nodes, links });
        setGraphError(null);
        setGraphLoading(false);
      })
      .catch((err: Error) => { if (!cancelled) { setGraphError(err.message); setGraphLoading(false); } });
    return () => { cancelled = true; };
  }, [kindFilter]);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetch("/api/entities/_kinds")
        .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
        .then((d: KindsSummary) => { if (!cancelled) setKindsSummary(d); })
        .catch(() => { /* non-fatal */ });
    };
    load();
    const h = window.setInterval(load, 10_000);
    return () => { cancelled = true; window.clearInterval(h); };
  }, []);

  useEffect(() => {
    if (!selectedId) { setSelectedPayload(null); setSelectedTimeline([]); return; }
    let cancelled = false;
    Promise.all([
      fetch(`/api/entities/${encodeURIComponent(selectedId)}`).then((r) => r.ok ? r.json() : null),
      fetch(`/api/entities/${encodeURIComponent(selectedId)}/timeline?limit=30`).then((r) => r.ok ? r.json() : []),
    ]).then(([payload, timeline]) => {
      if (cancelled) return;
      setSelectedPayload(payload ?? null);
      setSelectedTimeline(Array.isArray(timeline) ? timeline : []);
    });
    return () => { cancelled = true; };
  }, [selectedId]);

  const neighborIndex = useMemo(() => {
    const idx: Record<string, Set<string>> = {};
    for (const l of graph.links) {
      const s = typeof l.source === "string" ? l.source : l.source.id;
      const t = typeof l.target === "string" ? l.target : l.target.id;
      (idx[s] ??= new Set()).add(t);
      (idx[t] ??= new Set()).add(s);
    }
    return idx;
  }, [graph.links]);

  const heatmap = useMemo(() => {
    const idToKind: Record<string, string> = {};
    for (const n of graph.nodes) idToKind[n.id] = n.kind;
    const cells: Record<string, number> = {};
    let max = 0;
    for (const l of graph.links) {
      const s = typeof l.source === "string" ? l.source : l.source.id;
      const t = typeof l.target === "string" ? l.target : l.target.id;
      const sk = idToKind[s] ?? "?";
      const tk = idToKind[t] ?? "?";
      const key = `${sk}→${tk}`;
      cells[key] = (cells[key] ?? 0) + 1;
      if (cells[key] > max) max = cells[key];
    }
    return { cells, max };
  }, [graph]);

  const presentKinds = useMemo(() => {
    const present = new Set(graph.nodes.map((n) => n.kind));
    return KINDS.filter((k) => present.has(k));
  }, [graph.nodes]);

  const kindCounts: Record<string, number> = useMemo(() => {
    const out: Record<string, number> = {};
    for (const row of kindsSummary?.kinds ?? []) out[row.kind] = row.count;
    return out;
  }, [kindsSummary]);

  const totalEntities = useMemo(
    () => Object.values(kindCounts).reduce((a, b) => a + (b ?? 0), 0),
    [kindCounts],
  );

  return (
    <div className="flex-1 min-w-0 overflow-y-auto bg-slate-50 dark:bg-slate-950 p-6">
      <div className="max-w-[1600px] mx-auto space-y-3">
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1 dark:text-slate-400 dark:hover:text-slate-100"
          ><ArrowLeft size={14} /> Back to feed</Link>
        </div>

        <header className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Network size={18} className="text-slate-500 dark:text-slate-400" />
            <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Knowledge</h1>
            <span className="text-xs text-slate-500 dark:text-slate-400">the entity graph, live</span>
          </div>
          <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-2">
            <RefreshCw size={12} className={graphLoading ? "animate-spin" : "animate-pulse"} />
            <span>
              {graph.nodes.length} nodes · {graph.links.length} edges
              {totalEntities > 0 ? <> &nbsp;·&nbsp; {totalEntities.toLocaleString()} total in Kuzu</> : null}
            </span>
          </div>
        </header>

        <section className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-[11px] uppercase tracking-wide text-slate-400 dark:text-slate-500 px-1 mr-1">
              Kind
            </h2>
            {KINDS.map((k) => {
              const c = kindCounts[k] ?? 0;
              const active = k === kindFilter;
              return (
                <button
                  key={k}
                  type="button"
                  onClick={() => setKindFilter(active ? null : k)}
                  className={
                    "text-[11px] px-2 py-1 rounded inline-flex items-center gap-1.5 transition border " +
                    (active
                      ? "border-blue-500 bg-blue-50 dark:bg-blue-900/30 dark:border-blue-400 text-slate-900 dark:text-slate-100"
                      : "border-slate-200 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 text-slate-700 dark:text-slate-300")
                  }
                >
                  <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: colorForKind(k) }} />
                  <span>{k}</span>
                  <span className="text-slate-400 dark:text-slate-500 tabular-nums">{c}</span>
                </button>
              );
            })}
            {kindFilter && (
              <button
                type="button"
                onClick={() => setKindFilter(null)}
                className="ml-1 text-[11px] text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 flex items-center gap-1"
              ><X size={11} /> clear</button>
            )}
          </div>
        </section>

        <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-3">
          <section className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <h2 className="text-[11px] uppercase tracking-wide text-slate-400 dark:text-slate-500">Graph</h2>
                {graphError && <span className="text-[11px] text-rose-500">{graphError}</span>}
              </div>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-500 dark:text-slate-400 max-w-[60%] justify-end">
                {presentKinds.slice(0, 10).map((k) => (
                  <span key={k} className="flex items-center gap-1">
                    <span className="inline-block w-2 h-2 rounded-full" style={{ background: colorForKind(k) }} />
                    {k}
                  </span>
                ))}
                {presentKinds.length > 10 && <span>+{presentKinds.length - 10}</span>}
              </div>
            </div>
            <div ref={containerRef} className="w-full h-[640px] bg-slate-50 dark:bg-slate-950">
              <ForceGraph2D
                ref={fgRef}
                graphData={graph}
                width={size.w}
                height={size.h}
                backgroundColor="rgba(0,0,0,0)"
                cooldownTicks={120}
                d3VelocityDecay={0.3}
                linkColor={(l) => {
                  const link = l as unknown as GraphLink;
                  const s = typeof link.source === "string" ? link.source : link.source.id;
                  const t = typeof link.target === "string" ? link.target : link.target.id;
                  if (hoverId && (s === hoverId || t === hoverId)) return "rgba(59,130,246,0.9)";
                  if (selectedId && (s === selectedId || t === selectedId)) return "rgba(59,130,246,0.7)";
                  return "rgba(148,163,184,0.25)";
                }}
                linkDirectionalArrowLength={3}
                linkDirectionalArrowRelPos={0.85}
                linkWidth={(l) => {
                  const link = l as unknown as GraphLink;
                  const s = typeof link.source === "string" ? link.source : link.source.id;
                  const t = typeof link.target === "string" ? link.target : link.target.id;
                  if (hoverId && (s === hoverId || t === hoverId)) return 1.6;
                  if (selectedId && (s === selectedId || t === selectedId)) return 1.3;
                  return 0.6;
                }}
                nodeRelSize={4}
                nodeVal={(n) => Math.max(1, (n as GraphNode).__degree ?? 1)}
                nodeColor={(n) => {
                  const node = n as GraphNode;
                  if (selectedId && node.id === selectedId) return "#2563eb";
                  if (hoverId === node.id) return "#1d4ed8";
                  if (hoverId && neighborIndex[hoverId]?.has(node.id)) return "#60a5fa";
                  return colorForKind(node.kind);
                }}
                nodeCanvasObjectMode={() => "after"}
                nodeCanvasObject={(n, ctx, scale) => {
                  const node = n as GraphNode;
                  if (node.x === undefined || node.y === undefined) return;
                  if (scale < 1.6 && node.id !== selectedId && node.id !== hoverId) return;
                  const label = node.id.length <= 12 ? node.id : node.id.slice(0, 5) + "…" + node.id.slice(-4);
                  ctx.font = `${10 / scale}px ui-sans-serif, system-ui`;
                  ctx.fillStyle = "rgba(15,23,42,0.85)";
                  ctx.textAlign = "center";
                  ctx.textBaseline = "top";
                  ctx.fillText(label, node.x, node.y + 6 / scale);
                }}
                onNodeHover={(n) => setHoverId(n ? (n as GraphNode).id : null)}
                onNodeClick={(n) => {
                  const node = n as GraphNode;
                  setSelectedId(node.id);
                  if (fgRef.current && node.x !== undefined && node.y !== undefined) {
                    fgRef.current.centerAt(node.x, node.y, 600);
                    fgRef.current.zoom(2.4, 600);
                  }
                }}
                onBackgroundClick={() => setSelectedId(null)}
              />
            </div>
          </section>

          <aside className="space-y-3">
            <section className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3 min-h-[280px]">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-[11px] uppercase tracking-wide text-slate-400 dark:text-slate-500">
                  {selectedId ? "Selected entity" : "Selection"}
                </h2>
                {selectedId && (
                  <button
                    type="button"
                    onClick={() => setSelectedId(null)}
                    className="text-[11px] text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                  ><X size={12} /></button>
                )}
              </div>
              {!selectedId && (
                <p className="text-xs text-slate-400 dark:text-slate-500">
                  Click a node to pin it. Hover to highlight its 1-hop neighborhood.
                </p>
              )}
              {selectedId && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span
                      className="inline-block w-2.5 h-2.5 rounded-full"
                      style={{ background: colorForKind(selectedPayload?._label as string | undefined) }}
                    />
                    <span className="text-xs font-mono text-slate-800 dark:text-slate-200">{selectedId}</span>
                  </div>
                  {selectedPayload && (
                    <>
                      <div className="text-xs text-slate-600 dark:text-slate-300">
                        <span className="text-slate-400">kind:</span> {(selectedPayload._label as string) ?? "?"}
                        {selectedPayload.name ? <> &nbsp;·&nbsp; <span className="font-medium">{selectedPayload.name as string}</span></> : null}
                      </div>
                      <div className="rounded bg-slate-100 dark:bg-slate-950 p-2 max-h-44 overflow-y-auto">
                        <pre className="text-[10px] leading-tight text-slate-700 dark:text-slate-300 whitespace-pre-wrap font-mono">
{JSON.stringify(
  Object.fromEntries(
    Object.entries(selectedPayload).filter(([k]) => !k.startsWith("_") && k !== "id"),
  ),
  null,
  2,
)}
                        </pre>
                      </div>
                    </>
                  )}
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1">
                      Timeline ({selectedTimeline.length})
                    </div>
                    <div className="space-y-0.5 max-h-44 overflow-y-auto">
                      {selectedTimeline.length === 0 && (
                        <div className="text-xs text-slate-400">no audit entries</div>
                      )}
                      {selectedTimeline.map((row, i) => (
                        <div key={i} className="text-[11px] text-slate-600 dark:text-slate-300 truncate">
                          <span className="text-slate-400">
                            {row.timestamp ? new Date(row.timestamp * 1000).toLocaleTimeString() : "—"}
                          </span>
                          &nbsp;{row.summary ?? row.action ?? "(event)"}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </section>

            <section className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3">
              <h2 className="text-[11px] uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
                Edge density (kind → kind)
              </h2>
              {heatmap.max === 0 ? (
                <div className="text-xs text-slate-400">no edges in current view</div>
              ) : (
                <Heatmap cells={heatmap.cells} max={heatmap.max} kinds={presentKinds} />
              )}
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}

function Heatmap({
  cells, max, kinds,
}: {
  cells: Record<string, number>;
  max: number;
  kinds: readonly string[];
}) {
  const labelW = 60;
  const cellSize = 16;
  const w = labelW + kinds.length * cellSize;
  const h = labelW + kinds.length * cellSize;
  return (
    <div className="overflow-x-auto">
      <svg width={w} height={h} className="text-slate-600 dark:text-slate-300">
        {kinds.map((k, i) => (
          <text
            key={`c-${k}`}
            x={labelW + i * cellSize + cellSize / 2}
            y={labelW - 4}
            transform={`rotate(-60 ${labelW + i * cellSize + cellSize / 2} ${labelW - 4})`}
            textAnchor="start"
            className="fill-current"
            fontSize={9}
          >{k}</text>
        ))}
        {kinds.map((k, i) => (
          <text
            key={`r-${k}`}
            x={labelW - 4}
            y={labelW + i * cellSize + cellSize / 2 + 3}
            textAnchor="end"
            className="fill-current"
            fontSize={9}
          >{k}</text>
        ))}
        {kinds.map((src, i) =>
          kinds.map((dst, j) => {
            const v = cells[`${src}→${dst}`] ?? 0;
            const alpha = v === 0 ? 0 : 0.15 + 0.85 * (v / max);
            return (
              <rect
                key={`${src}-${dst}`}
                x={labelW + j * cellSize}
                y={labelW + i * cellSize}
                width={cellSize - 1}
                height={cellSize - 1}
                fill={v === 0 ? "rgba(148,163,184,0.06)" : `rgba(59,130,246,${alpha})`}
              >
                <title>{`${src} → ${dst}: ${v}`}</title>
              </rect>
            );
          }),
        )}
      </svg>
    </div>
  );
}
