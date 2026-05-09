/**
 * Standalone /functions blueprint page (Phase 3 IP7 — TASK-041..-043).
 *
 * Polls `/api/functions` every 5 seconds and renders a 9-tile grid (one
 * tile per non-legacy function). Clicking a tile expands it inline to
 * show the owned-domains list and the persona-hierarchy tree.
 */

import { useEffect, useState } from "react";

type PersonaNode = {
  role: string;
  manages: PersonaNode[];
};

type FunctionEntry = {
  name: string;
  display: string;
  operatorSurface: string;
  ownsDomains: string[];
  ambientAgents: string[];
  kpis: string[];
  personaHierarchy: PersonaNode;
};

function PersonaTree({ node }: { node: PersonaNode }) {
  return (
    <ul className="functions-page__persona-tree">
      <li>
        <code>{node.role}</code>
        {node.manages.length > 0 && (
          <>
            {node.manages.map((child) => (
              <PersonaTree key={child.role} node={child} />
            ))}
          </>
        )}
      </li>
    </ul>
  );
}

export function FunctionsPage() {
  const [entries, setEntries] = useState<FunctionEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      fetch("/api/functions")
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
        .then((d: FunctionEntry[]) => {
          if (cancelled) return;
          setEntries(d);
          setError(null);
        })
        .catch((err: Error) => {
          if (cancelled) return;
          setError(err.message);
        });
    };
    load();
    const handle = window.setInterval(load, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(handle);
    };
  }, []);

  return (
    <div className="page functions-page">
      <header className="functions-page__header">
        <p className="subtitle">Function Fleet Managers</p>
        <h1 className="section-title">
          <em>Nine functions, one substrate.</em>
        </h1>
        <p className="functions-page__lede">
          Every business function gets its own Fleet Manager session, KPI
          set, persona hierarchy, and ambient watchers — composed from
          the same primitives.
        </p>
        <p>
          <a href="/">← Back to the blueprint</a>
        </p>
      </header>

      {error && (
        <p className="functions-page__error">Failed to load: {error}</p>
      )}

      <section className="functions-page__grid">
        {entries.map((entry) => {
          const isOpen = expanded === entry.name;
          return (
            <article
              key={entry.name}
              className={`functions-page__tile${isOpen ? " functions-page__tile--open" : ""}`}
              onClick={() =>
                setExpanded((cur) => (cur === entry.name ? null : entry.name))
              }
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setExpanded((cur) =>
                    cur === entry.name ? null : entry.name,
                  );
                }
              }}
            >
              <header className="functions-page__tile-head">
                <h3>{entry.display}</h3>
                <code>{entry.name}</code>
              </header>
              <dl className="functions-page__tile-meta">
                <div>
                  <dt>KPIs</dt>
                  <dd>{entry.kpis.length}</dd>
                </div>
                <div>
                  <dt>Ambient agents</dt>
                  <dd>{entry.ambientAgents.length}</dd>
                </div>
                <div>
                  <dt>Owned domains</dt>
                  <dd>{entry.ownsDomains.length}</dd>
                </div>
              </dl>

              {isOpen && (
                <div className="functions-page__tile-body">
                  <div>
                    <p className="functions-page__label">Operator surface</p>
                    <code>{entry.operatorSurface}</code>
                  </div>
                  <div>
                    <p className="functions-page__label">KPIs</p>
                    {entry.kpis.length === 0 ? (
                      <p className="functions-page__empty">— none —</p>
                    ) : (
                      <ul className="functions-page__list">
                        {entry.kpis.map((k) => (
                          <li key={k}>
                            <code>{k}</code>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div>
                    <p className="functions-page__label">Owned domains</p>
                    {entry.ownsDomains.length === 0 ? (
                      <p className="functions-page__empty">— none —</p>
                    ) : (
                      <ul className="functions-page__list">
                        {entry.ownsDomains.map((d) => (
                          <li key={d}>
                            <code>{d}</code>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div>
                    <p className="functions-page__label">Ambient agents</p>
                    {entry.ambientAgents.length === 0 ? (
                      <p className="functions-page__empty">— none —</p>
                    ) : (
                      <ul className="functions-page__list">
                        {entry.ambientAgents.map((a) => (
                          <li key={a}>
                            <code>{a}</code>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div>
                    <p className="functions-page__label">Persona hierarchy</p>
                    <PersonaTree node={entry.personaHierarchy} />
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </section>
    </div>
  );
}
