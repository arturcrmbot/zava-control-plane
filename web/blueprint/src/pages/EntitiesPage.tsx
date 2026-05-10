/**
 * Standalone /entities observatory page (Phase 1 TASK-036).
 *
 * Three panels stacked vertically:
 *   1. Per-kind count tiles (the seven non-Workflow kinds).
 *   2. Kind-filtered entity table fetched on dropdown change.
 *   3. Recent-links pulse from the latest /_stats sample.
 *
 * Polls /api/entities/_stats every 5 seconds (cleanup clears the interval).
 * The dev server proxies /api → FastAPI on :3001 via vite.config.ts, so the
 * relative URLs match the rest of the blueprint app (useAuthority, etc.).
 */

import { useEffect, useState } from "react";

// The seven kinds the plan calls out. Workflow is intentionally omitted from
// this UI surface even though the API exposes it as the eighth node table.
const KINDS = [
  "Person",
  "Organisation",
  "Asset",
  "Money",
  "Decision",
  "Place",
  "Period",
] as const;

type Kind = (typeof KINDS)[number];

// Entity rows come from Kuzu in snake_case (see entities.py docstring).
type EntityRow = {
  id?: string;
  name?: string;
  source_workflows?: string[];
  [k: string]: unknown;
};

type RecentLink = {
  src: EntityRow;
  rel: string;
  dst: EntityRow;
};

type StatsResponse = {
  counts: Record<string, number>;
  hot: EntityRow[];
  recentLinks: RecentLink[];
};

function entityId(e: EntityRow | undefined): string {
  if (!e) return "?";
  const id = e.id;
  return typeof id === "string" && id.length > 0 ? id : "?";
}

export function EntitiesPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);

  const [selectedKind, setSelectedKind] = useState<Kind>("Person");
  const [rows, setRows] = useState<EntityRow[]>([]);
  const [rowsError, setRowsError] = useState<string | null>(null);
  const [rowsLoading, setRowsLoading] = useState(false);

  // Poll _stats every 5 seconds. Cleanup MUST clear the interval AND mark
  // the closure cancelled so a late fetch from the previous mount can't
  // race a setState into an unmounted component.
  useEffect(() => {
    let cancelled = false;

    const load = () => {
      fetch("/api/entities/_stats")
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
        .then((d: StatsResponse) => {
          if (cancelled) return;
          setStats(d);
          setStatsError(null);
        })
        .catch((err: Error) => {
          if (cancelled) return;
          setStatsError(err.message);
        });
    };

    load();
    const handle = window.setInterval(load, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(handle);
    };
  }, []);

  // Refetch the table whenever the kind dropdown changes.
  useEffect(() => {
    let cancelled = false;
    setRowsLoading(true);
    fetch(`/api/entities?kind=${encodeURIComponent(selectedKind)}&limit=50`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d: EntityRow[]) => {
        if (cancelled) return;
        setRows(Array.isArray(d) ? d : []);
        setRowsError(null);
        setRowsLoading(false);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setRowsError(err.message);
        setRowsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedKind]);

  const counts = stats?.counts ?? {};
  const recentLinks = (stats?.recentLinks ?? []).slice(0, 20);

  return (
    <div className="entities-page">
      <header className="entities-page__header">
        <div className="entities-page__eyebrow">the entity graph, live</div>
        <div className="entities-page__return">
          <a href="/">← return to the page</a>
        </div>
      </header>

      <main className="entities-page__main">
        <section className="entities-page__panel">
          <h2 className="entities-page__panel-title">Counts by kind</h2>
          {statsError && (
            <div className="entities-page__error">stats unavailable: {statsError}</div>
          )}
          <div className="entities-page__tiles">
            {KINDS.map((k) => (
              <div className="entities-page__tile" key={k}>
                <div className="entities-page__tile-kind">{k}</div>
                <div className="entities-page__tile-count">
                  {counts[k] ?? 0}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="entities-page__panel">
          <div className="entities-page__panel-head">
            <h2 className="entities-page__panel-title">Entities</h2>
            <label className="entities-page__select-label">
              kind&nbsp;
              <select
                className="entities-page__select"
                value={selectedKind}
                onChange={(e) => setSelectedKind(e.target.value as Kind)}
              >
                {KINDS.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {rowsError && (
            <div className="entities-page__error">{rowsError}</div>
          )}
          <table className="entities-page__table">
            <thead>
              <tr>
                <th>id</th>
                <th>name</th>
                <th>source_workflows</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && !rowsLoading && !rowsError && (
                <tr>
                  <td colSpan={3} className="entities-page__empty">
                    no {selectedKind} entities
                  </td>
                </tr>
              )}
              {rowsLoading && rows.length === 0 && (
                <tr>
                  <td colSpan={3} className="entities-page__empty">
                    loading…
                  </td>
                </tr>
              )}
              {rows.map((row, i) => {
                const sw = Array.isArray(row.source_workflows)
                  ? row.source_workflows
                  : [];
                return (
                  <tr key={`${entityId(row)}-${i}`}>
                    <td className="entities-page__mono">{entityId(row)}</td>
                    <td>{typeof row.name === "string" ? row.name : ""}</td>
                    <td className="entities-page__mono">
                      {sw.length === 0 ? "—" : sw.join(", ")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        <section className="entities-page__panel">
          <h2 className="entities-page__panel-title">Recent links</h2>
          <div className="entities-page__pulse">
            {recentLinks.length === 0 ? (
              <div className="entities-page__empty">no links yet</div>
            ) : (
              recentLinks.map((link, i) => (
                <div className="entities-page__pulse-row" key={i}>
                  <span className="entities-page__mono">{entityId(link.src)}</span>
                  <span className="entities-page__pulse-arrow">
                    {" "}--[{link.rel}]--&gt;{" "}
                  </span>
                  <span className="entities-page__mono">{entityId(link.dst)}</span>
                </div>
              ))
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
