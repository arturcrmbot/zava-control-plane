/**
 * /admin/org-clone observatory — Phase 4 IP7 (TASK-036).
 *
 * Single-page operator view that fans out across the four read APIs the
 * substrate exposes for the agentic-org plane:
 *
 *   1. /api/entities/_stats          → entity counts + hot list
 *   2. /api/workflows                → in-flight workflows (filtered to meta-types)
 *      /api/workflows/{id}/tree      → per-meta-workflow recursive tree
 *   3. /api/functions/{name}/ambient → ambient agents per function
 *   4. /api/functions                → function FMs + last-cycle KPIs
 *   5. /api/cadences                 → cadence schedule + next_run_at
 *
 * Polls every 8 seconds. Style mirrors EntitiesPage / FunctionsPage.
 */

import { useEffect, useState } from "react";

type EntityCounts = Record<string, number>;
type StatsResponse = { counts: EntityCounts };

type FunctionEntry = {
  name: string;
  display: string;
  ownsDomains: string[];
  ambientAgents: string[];
  kpis: string[];
};

type AmbientAgentRow = {
  name: string;
  function: string;
  triggers: Array<Record<string, unknown>>;
  spawnable_workflow_types: string[];
  reasoning_skill: string | null;
  last_trigger_at: number | null;
  last_spawn_outcome: Record<string, unknown> | null;
  is_killed: boolean;
};

type CadenceRow = {
  name: string;
  schedule: string;
  fires_ambient_agent: string;
  next_run_at: string | null;
};

type WorkflowSummary = {
  id: string;
  type: string;
  status: string;
};

type TreeNode = {
  workflow_id: string;
  workflow_type: string | null;
  status: string;
  children: TreeNode[];
};

const META_TYPES = new Set([
  "fy-close",
  "board-prep",
  "okr-quarterly-review",
]);

function panelStyle(): React.CSSProperties {
  return {
    border: "1px solid #ccd",
    borderRadius: 8,
    padding: "16px 20px",
    marginBottom: 18,
    background: "#fafbff",
  };
}

function Tree({ node }: { node: TreeNode }) {
  return (
    <ul style={{ marginLeft: 12, paddingLeft: 12, borderLeft: "1px solid #ccd" }}>
      <li>
        <code>{node.workflow_id}</code>{" "}
        <span style={{ color: "#666", fontSize: "0.9em" }}>
          ({node.workflow_type ?? "?"} · {node.status})
        </span>
        {node.children.map((c) => (
          <Tree key={c.workflow_id} node={c} />
        ))}
      </li>
    </ul>
  );
}

export function OrgClonePage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [functions, setFunctions] = useState<FunctionEntry[]>([]);
  const [cadences, setCadences] = useState<CadenceRow[]>([]);
  const [ambientByFn, setAmbientByFn] = useState<Record<string, AmbientAgentRow[]>>({});
  const [trees, setTrees] = useState<TreeNode[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const [statsR, fnR, cadR, wfR] = await Promise.all([
          fetch("/api/entities/_stats").then((r) => r.json()),
          fetch("/api/functions").then((r) => r.json()),
          fetch("/api/cadences").then((r) => r.json()),
          fetch("/api/workflows").then((r) => r.json()),
        ]);
        if (cancelled) return;
        setStats(statsR);
        setFunctions(fnR);
        setCadences(cadR);

        const ambient: Record<string, AmbientAgentRow[]> = {};
        await Promise.all(
          fnR.map(async (fn: FunctionEntry) => {
            try {
              const r = await fetch(`/api/functions/${fn.name}/ambient`);
              if (r.ok) ambient[fn.name] = await r.json();
            } catch {
              // ignore — partial fan-out is acceptable for the observatory
            }
          })
        );
        if (cancelled) return;
        setAmbientByFn(ambient);

        const metaWfs = (wfR as WorkflowSummary[]).filter((w) =>
          META_TYPES.has(w.type)
        );
        const treeRows = await Promise.all(
          metaWfs.map(async (w) => {
            const r = await fetch(`/api/workflows/${w.id}/tree`);
            return (await r.json()) as TreeNode;
          })
        );
        if (cancelled) return;
        setTrees(treeRows);
        setError(null);
      } catch (ex) {
        if (!cancelled) setError(String(ex));
      }
    };

    load();
    const id = window.setInterval(load, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return (
    <div style={{ maxWidth: 1100, margin: "30px auto", padding: 20, fontFamily: "system-ui, sans-serif" }}>
      <h1>Org Clone — Live Observatory</h1>
      <p style={{ color: "#666" }}>
        Five-panel view of the agentic-org substrate. Polls every 8 seconds.
      </p>
      {error && <div style={{ color: "crimson" }}>Error: {error}</div>}

      {/* Panel 1 — entity counts */}
      <section style={panelStyle()}>
        <h2>1. Entities</h2>
        {stats ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
            {Object.entries(stats.counts).map(([k, v]) => (
              <div key={k} style={{ padding: 8, background: "#fff", borderRadius: 4, textAlign: "center" }}>
                <div style={{ fontSize: "0.85em", color: "#666" }}>{k}</div>
                <div style={{ fontSize: "1.4em", fontWeight: 600 }}>{v}</div>
              </div>
            ))}
          </div>
        ) : (
          <div>Loading…</div>
        )}
      </section>

      {/* Panel 2 — meta-workflow trees */}
      <section style={panelStyle()}>
        <h2>2. Meta-workflow trees</h2>
        {trees.length === 0 ? (
          <div style={{ color: "#888" }}>No in-flight meta-workflows.</div>
        ) : (
          trees.map((t) => <Tree key={t.workflow_id} node={t} />)
        )}
      </section>

      {/* Panel 3 — ambient agents per function */}
      <section style={panelStyle()}>
        <h2>3. Ambient agents</h2>
        {functions.map((fn) => {
          const rows = ambientByFn[fn.name] || [];
          if (rows.length === 0) return null;
          return (
            <div key={fn.name} style={{ marginBottom: 14 }}>
              <h3 style={{ margin: "8px 0 4px" }}>{fn.display}</h3>
              <table style={{ width: "100%", fontSize: "0.9em", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "#eef" }}>
                    <th style={{ textAlign: "left", padding: 4 }}>Name</th>
                    <th style={{ textAlign: "left", padding: 4 }}>Triggers</th>
                    <th style={{ textAlign: "left", padding: 4 }}>Spawnable</th>
                    <th style={{ textAlign: "left", padding: 4 }}>Last fire</th>
                    <th style={{ textAlign: "left", padding: 4 }}>Killed?</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((a) => (
                    <tr key={a.name} style={{ borderBottom: "1px solid #eee" }}>
                      <td style={{ padding: 4 }}><code>{a.name}</code></td>
                      <td style={{ padding: 4 }}>
                        {a.triggers.map((t, i) => (
                          <span key={i} style={{ marginRight: 6 }}>
                            {String(t.kind)}
                          </span>
                        ))}
                      </td>
                      <td style={{ padding: 4 }}>{a.spawnable_workflow_types.join(", ") || "—"}</td>
                      <td style={{ padding: 4 }}>
                        {a.last_trigger_at
                          ? new Date(a.last_trigger_at * 1000).toLocaleTimeString()
                          : "—"}
                      </td>
                      <td style={{ padding: 4 }}>{a.is_killed ? "🛑" : "✓"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        })}
      </section>

      {/* Panel 4 — function FMs */}
      <section style={panelStyle()}>
        <h2>4. Function FMs</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
          {functions.map((fn) => (
            <div key={fn.name} style={{ padding: 10, background: "#fff", borderRadius: 4, border: "1px solid #ddd" }}>
              <div style={{ fontWeight: 600 }}>{fn.display}</div>
              <div style={{ fontSize: "0.85em", color: "#666", marginTop: 4 }}>
                {fn.ownsDomains.length} domains · {fn.ambientAgents.length} ambient · {fn.kpis.length} KPIs
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Panel 5 — cadences */}
      <section style={panelStyle()}>
        <h2>5. Cadences</h2>
        <table style={{ width: "100%", fontSize: "0.9em", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#eef" }}>
              <th style={{ textAlign: "left", padding: 4 }}>Name</th>
              <th style={{ textAlign: "left", padding: 4 }}>Schedule</th>
              <th style={{ textAlign: "left", padding: 4 }}>Fires</th>
              <th style={{ textAlign: "left", padding: 4 }}>Next run</th>
            </tr>
          </thead>
          <tbody>
            {cadences.map((c) => (
              <tr key={c.name} style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: 4 }}><code>{c.name}</code></td>
                <td style={{ padding: 4 }}><code>{c.schedule}</code></td>
                <td style={{ padding: 4 }}>{c.fires_ambient_agent}</td>
                <td style={{ padding: 4 }}>{c.next_run_at ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
