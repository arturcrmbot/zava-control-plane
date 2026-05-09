/**
 * The Org Building (IP7, TASK-035..-040) — department interior overlay.
 *
 * Mounted at zoom-level 1. Renders a top-down floor plan for one
 * function: corner-office FM tile, indented persona desks (hierarchy
 * order), workstation tiles per owned-domain, ambient-sensor tiles per
 * ambient agent, a 7-icon entity vault wall, KPI clipboards (with
 * sparklines from `?history=30`), and a wall-calendar tile.
 *
 * Implementation: DOM overlay (same pattern as `EventFeed`) so we
 * don't pay R3F costs for the interior cutaway. The 3D scene continues
 * to render behind and the camera tween settles into a low-detail
 * close-up; the operator sees the interior on top of the building.
 *
 * Click handlers:
 *   - workstation → fetch in-flight workflows for that domain;
 *     fire `org-building:zoom-to {kind:'workflow', id:<wf_id>}`.
 *   - persona desk → fetch `/api/persona/{role}/recent`; show in a
 *     small inline panel.
 *   - vault icon → opens the entity-list mini-panel filtered to that
 *     kind; clicking an entity emits `org-building:entity-selected`.
 *
 * Live event animations (TASK-039) — subscribes to the SSE stream and
 * paints light decorations on:
 *   - the persona desk that just decided (decision spark)
 *   - the entity vault tile of the matching kind (entity mote)
 *   - the ambient sensor that just fired (ambient flash)
 *   - workstation→workstation (sub-spawned filament)
 * Effects are CSS-only — short pulses keyed on a per-target counter.
 */
import { useEffect, useMemo, useState } from "react";

import { useObservatory } from "../../lib/useObservatory";
import { useOrgData } from "../../lib/useOrgData";
import { cadencesFor } from "../../lib/cadenceMapping";
import { COLORS } from "../../lib/orgEvents";
import type { OrgFunction, Cadence } from "../../lib/useOrgData";
import type { ObservatoryEvent } from "../../lib/types";

const VAULT_KINDS = [
  "Person",
  "Organisation",
  "Asset",
  "Money",
  "Decision",
  "Place",
  "Period",
] as const;
type VaultKind = (typeof VAULT_KINDS)[number];

const VAULT_COLORS: Record<VaultKind, string> = {
  Person: "#7faed4",
  Organisation: "#f4a300",
  Asset: "#5fb3a8",
  Money: "#ffd76a",
  Decision: COLORS.decision,
  Place: "#5fd49d",
  Period: "#f1f1f1",
};

interface PersonaNode {
  role: string;
  manages: PersonaNode[];
}

interface KpiHistory {
  metrics: Record<
    string,
    { value: number; period: string; captured_at: number } | undefined
  >;
  history?: Record<string, { value: number; captured_at: number }[]>;
}

interface PendingGate {
  workflow_id: string;
  workflow_type: string;
  gate_id: string | null;
  name: string | null;
  persona_role: string;
  opened_at: number | null;
  status: string;
}
interface RecentDecision {
  decision_id: string | null;
  workflow_id: string | null;
  persona_role: string;
  verdict: string | null;
  reason: string | null;
  decided_at: number | null;
}
interface PersonaRecent {
  role: string;
  pending_gates: PendingGate[];
  recent_decisions: RecentDecision[];
}

/** Flatten a persona-hierarchy tree into ``[{role, depth}, ...]`` rows
 *  in pre-order traversal, so the indented desk list reads top-down. */
export function flattenPersonas(
  node: PersonaNode | null | undefined,
  depth = 0,
  out: { role: string; depth: number }[] = [],
): { role: string; depth: number }[] {
  if (!node || !node.role) return out;
  out.push({ role: node.role, depth });
  for (const child of node.manages ?? []) {
    flattenPersonas(child, depth + 1, out);
  }
  return out;
}

/** Map an entity-touched count (per kind) for a function. Joins
 *  ``hotEntities`` (whose ``source_workflows`` we know) against the
 *  function's ``ownsDomains`` set. Best-effort: hot is a top-N sample,
 *  not the full graph; the count is "≥ N seen recently". */
export function countTouchedByFunction(
  fn: OrgFunction,
  hot: { kind: string; source_workflows: string[] }[],
): Record<VaultKind, number> {
  const owned = new Set(fn.ownsDomains);
  const out: Record<string, number> = {};
  for (const k of VAULT_KINDS) out[k] = 0;
  for (const ent of hot) {
    if (!ent.source_workflows?.some((wt) => owned.has(wt))) continue;
    const k = ent.kind as VaultKind;
    if (k in out) out[k] += 1;
  }
  return out as Record<VaultKind, number>;
}

interface Props {
  name: string;
  /** Optional click-to-zoom handler. When omitted, fires the
   *  `org-building:zoom-to` event so the page-level zoom hook catches
   *  it. */
  onZoomTo?: (target: { kind: "workflow" | "department"; id: string }) => void;
  /** Closes the interior overlay (ESC handler / explicit "back"). */
  onClose: () => void;
}

export function DepartmentInterior({ name, onZoomTo, onClose }: Props) {
  const snap = useOrgData();
  const fn = snap.functionByName.get(name);
  const cadences = useMemo(
    () => snap.cadences.filter((c) => cadencesFor(name).includes(c.name as never)),
    [snap.cadences, name],
  );
  const counts = useMemo(
    () => (fn ? countTouchedByFunction(fn, snap.hotEntities) : (Object.fromEntries(VAULT_KINDS.map((k) => [k, 0])) as Record<VaultKind, number>)),
    [fn, snap.hotEntities],
  );

  const personas = useMemo(
    () => (fn ? flattenPersonas(fn.personaHierarchy as PersonaNode) : []),
    [fn],
  );

  // KPI history poll
  const [kpis, setKpis] = useState<KpiHistory>({ metrics: {}, history: {} });
  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    async function tick() {
      try {
        const r = await fetch(
          `/api/functions/${encodeURIComponent(name)}/kpis-latest?history=30`,
        );
        if (r.ok && !cancelled) setKpis(await r.json());
      } catch {
        /* keep last */
      } finally {
        if (!cancelled) timer = window.setTimeout(tick, 5000);
      }
    }
    tick();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [name]);

  // SSE-driven event decorations
  const [pulses, setPulses] = useState<Record<string, number>>({});
  function pulse(key: string) {
    setPulses((cur) => ({ ...cur, [key]: (cur[key] ?? 0) + 1 }));
    window.setTimeout(() => {
      setPulses((cur) => {
        const v = (cur[key] ?? 0) - 1;
        const next = { ...cur };
        if (v <= 0) delete next[key];
        else next[key] = v;
        return next;
      });
    }, 1400);
  }
  useObservatory({
    bufferSize: 1,
    onEvent: (event: ObservatoryEvent) => {
      const wt = event.workflow_type ?? "";
      const matchesDomain = fn?.ownsDomains.includes(wt) ?? false;
      const matchesFn = event.function === name || matchesDomain;
      if (!matchesFn) return;
      switch (event.type) {
        case "decision.recorded":
          if (event.persona) pulse(`desk:${event.persona}`);
          break;
        case "entity.upserted":
          if (event.entity_kind) pulse(`vault:${event.entity_kind}`);
          break;
        case "ambient.decided":
          if (event.ambient_agent) pulse(`sensor:${event.ambient_agent}`);
          break;
        case "workflow.sub_spawned":
          if (event.workflow_type) pulse(`workstation:${event.workflow_type}`);
          break;
      }
    },
  });

  // Persona panel state
  const [openPersona, setOpenPersona] = useState<PersonaRecent | null>(null);
  async function openPersonaSidebar(role: string) {
    try {
      const r = await fetch(`/api/persona/${encodeURIComponent(role)}/recent`);
      if (r.ok) setOpenPersona(await r.json());
    } catch {
      setOpenPersona({ role, pending_gates: [], recent_decisions: [] });
    }
  }

  // Vault panel state
  const [openVault, setOpenVault] = useState<VaultKind | null>(null);
  const [vaultEntities, setVaultEntities] = useState<{ id: string; kind: string }[]>([]);
  useEffect(() => {
    if (!openVault || !fn) return;
    let cancelled = false;
    fetch(`/api/entities?kind=${encodeURIComponent(openVault)}&limit=50`)
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: unknown[]) => {
        if (cancelled) return;
        const owned = new Set(fn.ownsDomains);
        const filtered = (rows as { id?: string; entity_id?: string; source_workflows?: string[] }[])
          .filter((e) => e.source_workflows?.some((wt) => owned.has(wt)))
          .map((e) => ({ id: (e.id ?? e.entity_id ?? "") as string, kind: openVault }));
        setVaultEntities(filtered);
      })
      .catch(() => setVaultEntities([]));
    return () => {
      cancelled = true;
    };
  }, [openVault, fn]);

  // Workstation click → in-flight workflows for that domain
  const [workstationPicker, setWorkstationPicker] = useState<{
    domain: string;
    items: { id: string; type: string; status: string }[];
  } | null>(null);
  async function clickWorkstation(domain: string) {
    try {
      const r = await fetch(
        `/api/workflows?status=in_progress`,
      );
      if (!r.ok) return;
      const all = (await r.json()) as { id: string; type: string; status: string }[];
      const matching = all.filter((w) => w.type === domain);
      if (matching.length === 0) return;
      if (matching.length === 1) {
        const tgt = { kind: "workflow" as const, id: matching[0].id };
        if (onZoomTo) onZoomTo(tgt);
        else
          window.dispatchEvent(
            new CustomEvent("org-building:zoom-to", { detail: tgt }),
          );
      } else {
        // sort by id (ULID-prefixed → newest first lexicographically)
        const sorted = [...matching].sort((a, b) => (a.id < b.id ? 1 : -1));
        setWorkstationPicker({ domain, items: sorted.slice(0, 10) });
      }
    } catch {
      /* swallow */
    }
  }

  if (!fn) {
    return (
      <div style={overlayStyle}>
        <div style={{ padding: 24, color: "#cfd2d6" }}>
          loading {name}…
          <button type="button" onClick={onClose} style={closeStyle}>
            ✕
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={overlayStyle} role="dialog" aria-label={`${fn.display} interior`}>
      <header style={headerStyle}>
        <div>
          <div style={{ fontSize: 11, color: "#9aa0a6", letterSpacing: "0.12em" }}>
            DEPARTMENT · ZOOM 1
          </div>
          <h2 style={{ margin: "4px 0 0", fontSize: 22, color: "#f5f5f7" }}>
            {fn.display}
          </h2>
        </div>
        <button type="button" onClick={onClose} style={closeStyle} aria-label="close">
          ✕
        </button>
      </header>

      <div style={gridStyle}>
        {/* Corner office FM tile */}
        <section style={{ ...tileStyle, gridColumn: "span 2" }}>
          <div style={tileLabel}>FM corner office</div>
          <div style={fmTileStyle(pulses[`fm:${name}`] ? 1 : 0)}>
            <div style={{ fontSize: 14, color: "#f5f5f7" }}>
              {fn.personaHierarchy?.role ?? "—"}
            </div>
            <div style={{ fontSize: 10, color: "#9aa0a6", marginTop: 2 }}>
              {fn.operatorSurface}
            </div>
          </div>
        </section>

        {/* Persona desks */}
        <section style={{ ...tileStyle, gridColumn: "span 3", gridRow: "span 2" }}>
          <div style={tileLabel}>Persona desks</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {personas.map(({ role, depth }) => (
              <button
                key={role}
                type="button"
                onClick={() => openPersonaSidebar(role)}
                style={deskStyle(depth, !!pulses[`desk:${role}`])}
              >
                <span style={{ opacity: 0.6, marginRight: 6 }}>
                  {"›".repeat(depth + 1)}
                </span>
                {role}
              </button>
            ))}
          </div>
        </section>

        {/* KPI clipboards */}
        <section style={{ ...tileStyle, gridColumn: "span 3" }}>
          <div style={tileLabel}>KPI wall</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
            {fn.kpis.map((metric) => (
              <KpiClipboard
                key={metric}
                metric={metric}
                latest={kpis.metrics?.[metric]?.value ?? null}
                history={(kpis.history?.[metric] ?? []).map((h) => h.value)}
              />
            ))}
            {fn.kpis.length === 0 && (
              <div style={{ color: "#6b7077", fontSize: 11 }}>no KPIs declared</div>
            )}
          </div>
        </section>

        {/* Workstations */}
        <section style={{ ...tileStyle, gridColumn: "span 3" }}>
          <div style={tileLabel}>Workstations · owned domains</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {fn.ownsDomains.map((dom) => (
              <button
                key={dom}
                type="button"
                onClick={() => clickWorkstation(dom)}
                style={workstationStyle(!!pulses[`workstation:${dom}`])}
                title={`open in-flight workflow for ${dom}`}
              >
                <span aria-hidden style={{ fontSize: 16 }}>▭</span>
                <span style={{ fontSize: 10 }}>{dom}</span>
              </button>
            ))}
          </div>
        </section>

        {/* Ambient sensors */}
        <section style={{ ...tileStyle, gridColumn: "span 2" }}>
          <div style={tileLabel}>Ambient sensors</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {fn.ambientAgents.map((ag) => (
              <div
                key={ag}
                style={sensorStyle(!!pulses[`sensor:${ag}`])}
                aria-label={`ambient sensor ${ag}`}
              >
                <span aria-hidden>📷</span> <span style={{ fontSize: 10 }}>{ag}</span>
              </div>
            ))}
            {fn.ambientAgents.length === 0 && (
              <div style={{ color: "#6b7077", fontSize: 11 }}>none</div>
            )}
          </div>
        </section>

        {/* Cadence calendar */}
        <section style={{ ...tileStyle, gridColumn: "span 2" }}>
          <div style={tileLabel}>Cadence calendar</div>
          <CadenceCalendar cadences={cadences} />
        </section>

        {/* Entity vault wall */}
        <section style={{ ...tileStyle, gridColumn: "span 5" }}>
          <div style={tileLabel}>Entity vault</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 6 }}>
            {VAULT_KINDS.map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setOpenVault(k === openVault ? null : k)}
                style={vaultIconStyle(VAULT_COLORS[k], !!pulses[`vault:${k}`], openVault === k)}
              >
                <div style={{ fontSize: 11, color: VAULT_COLORS[k] }}>● {k}</div>
                <div style={{ fontSize: 14, color: "#f5f5f7" }}>{counts[k]}</div>
              </button>
            ))}
          </div>
          {openVault && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 10, color: "#9aa0a6", marginBottom: 4 }}>
                {openVault} · touched by {fn.display}
              </div>
              <div style={{ maxHeight: 110, overflowY: "auto" }}>
                {vaultEntities.length === 0 ? (
                  <div style={{ color: "#6b7077", fontSize: 11 }}>no recent matches</div>
                ) : (
                  vaultEntities.map((e) => (
                    <button
                      key={e.id}
                      type="button"
                      onClick={() =>
                        window.dispatchEvent(
                          new CustomEvent("org-building:entity-selected", {
                            detail: { entityId: e.id, source: "vault" },
                          }),
                        )
                      }
                      style={{
                        display: "block",
                        width: "100%",
                        textAlign: "left",
                        background: "transparent",
                        border: 0,
                        color: "#cfd2d6",
                        fontFamily: "inherit",
                        fontSize: 10,
                        padding: "2px 4px",
                        cursor: "pointer",
                      }}
                    >
                      {e.id}
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </section>
      </div>

      {openPersona && (
        <PersonaSidebar
          recent={openPersona}
          onClose={() => setOpenPersona(null)}
        />
      )}

      {workstationPicker && (
        <div style={pickerStyle}>
          <div style={{ fontSize: 11, color: "#9aa0a6", marginBottom: 6 }}>
            {workstationPicker.domain} — pick an in-flight workflow
          </div>
          {workstationPicker.items.map((w) => (
            <button
              key={w.id}
              type="button"
              onClick={() => {
                const tgt = { kind: "workflow" as const, id: w.id };
                if (onZoomTo) onZoomTo(tgt);
                else
                  window.dispatchEvent(
                    new CustomEvent("org-building:zoom-to", { detail: tgt }),
                  );
                setWorkstationPicker(null);
              }}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                background: "transparent",
                border: 0,
                color: "#cfd2d6",
                fontFamily: "inherit",
                fontSize: 11,
                padding: "3px 6px",
                cursor: "pointer",
              }}
            >
              {w.id}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setWorkstationPicker(null)}
            style={{ marginTop: 6, ...closeStyleSmall }}
          >
            cancel
          </button>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* sub-components + styles                                            */
/* ------------------------------------------------------------------ */

function KpiClipboard({
  metric,
  latest,
  history,
}: {
  metric: string;
  latest: number | null;
  history: number[];
}) {
  return (
    <div
      style={{
        background: "rgba(20,22,28,0.65)",
        border: "1px solid rgba(207,210,214,0.18)",
        borderRadius: 6,
        padding: 6,
      }}
    >
      <div style={{ fontSize: 9, color: "#9aa0a6", textTransform: "uppercase" }}>
        {metric}
      </div>
      <div style={{ fontSize: 14, color: "#f5f5f7" }}>
        {latest == null ? "—" : Math.abs(latest) >= 100 ? latest.toFixed(0) : latest.toFixed(1)}
      </div>
      <Sparkline values={history} />
    </div>
  );
}

export function Sparkline({ values }: { values: number[] }) {
  const w = 80;
  const h = 18;
  if (values.length < 2) {
    return (
      <svg width={w} height={h}>
        <line x1={0} y1={h / 2} x2={w} y2={h / 2} stroke="#3a3f48" strokeWidth={1} />
      </svg>
    );
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - ((v - min) / span) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={w} height={h}>
      <polyline points={pts} fill="none" stroke="#7faed4" strokeWidth={1.2} />
    </svg>
  );
}

function CadenceCalendar({ cadences }: { cadences: Cadence[] }) {
  if (cadences.length === 0) {
    return (
      <div style={{ color: "#6b7077", fontSize: 11 }}>
        no cadences mapped to this floor
      </div>
    );
  }
  const today = new Date();
  const days = Array.from({ length: 14 }, (_, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() + i);
    return d;
  });
  const fireDays = new Set<string>();
  for (const c of cadences) {
    if (c.next_run_at) {
      const d = new Date(c.next_run_at);
      fireDays.add(d.toDateString());
    }
  }
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 2 }}>
        {days.slice(0, 7).map((d) => (
          <DayCell key={d.toISOString()} d={d} fires={fireDays.has(d.toDateString())} />
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 2, marginTop: 2 }}>
        {days.slice(7).map((d) => (
          <DayCell key={d.toISOString()} d={d} fires={fireDays.has(d.toDateString())} />
        ))}
      </div>
      <div style={{ marginTop: 6, fontSize: 9, color: "#9aa0a6" }}>
        {cadences.map((c) => c.name).join(" · ")}
      </div>
    </div>
  );
}

function DayCell({ d, fires }: { d: Date; fires: boolean }) {
  return (
    <div
      style={{
        textAlign: "center",
        padding: "2px 0",
        fontSize: 9,
        background: fires ? "rgba(167,139,250,0.18)" : "rgba(40,44,52,0.4)",
        border: fires ? "1px solid #a78bfa" : "1px solid transparent",
        borderRadius: 3,
        color: fires ? "#f5f5f7" : "#9aa0a6",
      }}
    >
      {d.getDate()}
    </div>
  );
}

function PersonaSidebar({
  recent,
  onClose,
}: {
  recent: PersonaRecent;
  onClose: () => void;
}) {
  return (
    <aside
      style={{
        position: "absolute",
        top: 70,
        right: 12,
        width: 280,
        maxHeight: "70vh",
        overflowY: "auto",
        padding: 12,
        background: "rgba(15,17,22,0.95)",
        border: "1px solid rgba(207,210,214,0.25)",
        borderRadius: 8,
        color: "#cfd2d6",
        fontSize: 11,
        zIndex: 12,
      }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <strong style={{ color: "#f5f5f7", fontSize: 13 }}>{recent.role}</strong>
        <button type="button" onClick={onClose} style={closeStyleSmall}>
          ✕
        </button>
      </header>
      <div style={{ fontSize: 10, color: "#9aa0a6", marginBottom: 4 }}>
        Pending HITL gates ({recent.pending_gates.length})
      </div>
      {recent.pending_gates.length === 0 ? (
        <div style={{ color: "#6b7077", marginBottom: 8 }}>none</div>
      ) : (
        recent.pending_gates.slice(0, 5).map((g, i) => (
          <div key={i} style={{ marginBottom: 4 }}>
            <span style={{ color: COLORS.decision }}>⚖</span>{" "}
            {g.name ?? g.gate_id ?? "(gate)"} · {g.workflow_id}
          </div>
        ))
      )}
      <div style={{ fontSize: 10, color: "#9aa0a6", margin: "8px 0 4px" }}>
        Recent decisions ({recent.recent_decisions.length})
      </div>
      {recent.recent_decisions.length === 0 ? (
        <div style={{ color: "#6b7077" }}>none</div>
      ) : (
        recent.recent_decisions.slice(0, 5).map((d, i) => (
          <div key={i} style={{ marginBottom: 4 }}>
            <span style={{ color: COLORS.decision }}>●</span> {d.verdict ?? "?"}{" "}
            <span style={{ color: "#9aa0a6" }}>{d.workflow_id}</span>
          </div>
        ))
      )}
    </aside>
  );
}

const overlayStyle: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  background: "rgba(6,7,10,0.9)",
  zIndex: 10,
  padding: 18,
  color: "#cfd2d6",
  fontFamily: "var(--mono-family, monospace)",
  overflow: "auto",
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  marginBottom: 14,
};

const closeStyle: React.CSSProperties = {
  background: "rgba(20,22,28,0.7)",
  border: "1px solid rgba(207,210,214,0.3)",
  borderRadius: 999,
  color: "#cfd2d6",
  padding: "4px 10px",
  fontFamily: "inherit",
  cursor: "pointer",
};

const closeStyleSmall: React.CSSProperties = {
  background: "transparent",
  border: "1px solid rgba(207,210,214,0.25)",
  borderRadius: 4,
  color: "#9aa0a6",
  padding: "2px 6px",
  fontFamily: "inherit",
  fontSize: 10,
  cursor: "pointer",
};

const gridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(5, 1fr)",
  gap: 10,
  maxWidth: 1100,
  margin: "0 auto",
};

const tileStyle: React.CSSProperties = {
  background: "rgba(15,17,22,0.78)",
  border: "1px solid rgba(207,210,214,0.18)",
  borderRadius: 8,
  padding: 10,
};

const tileLabel: React.CSSProperties = {
  fontSize: 9,
  color: "#9aa0a6",
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  marginBottom: 6,
};

function fmTileStyle(active: number): React.CSSProperties {
  return {
    background: active
      ? "rgba(255,215,106,0.18)"
      : "rgba(40,44,52,0.55)",
    border: `1px solid ${active ? "#ffd76a" : "rgba(207,210,214,0.2)"}`,
    borderRadius: 6,
    padding: 8,
    transition: "background 0.4s ease, border 0.4s ease",
  };
}

function deskStyle(depth: number, active: boolean): React.CSSProperties {
  return {
    paddingLeft: 10 + depth * 12,
    padding: "4px 6px",
    paddingRight: 6,
    background: active ? "rgba(167,139,250,0.22)" : "transparent",
    border: 0,
    borderLeft: `2px solid ${active ? COLORS.decision : "rgba(207,210,214,0.15)"}`,
    color: "#cfd2d6",
    fontFamily: "inherit",
    fontSize: 11,
    textAlign: "left",
    cursor: "pointer",
    transition: "background 0.4s ease",
  };
}

function workstationStyle(active: boolean): React.CSSProperties {
  return {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 2,
    padding: "6px 8px",
    background: active ? "rgba(236,72,153,0.18)" : "rgba(20,22,28,0.65)",
    border: `1px solid ${active ? COLORS.subspawn : "rgba(207,210,214,0.18)"}`,
    borderRadius: 6,
    color: "#cfd2d6",
    fontFamily: "inherit",
    cursor: "pointer",
    minWidth: 80,
    transition: "background 0.4s ease",
  };
}

function sensorStyle(active: boolean): React.CSSProperties {
  return {
    padding: "4px 6px",
    background: active ? "rgba(251,191,36,0.2)" : "rgba(20,22,28,0.5)",
    border: `1px solid ${active ? COLORS.ambient : "rgba(207,210,214,0.18)"}`,
    borderRadius: 4,
    color: "#cfd2d6",
    fontSize: 11,
    transition: "background 0.4s ease",
  };
}

function vaultIconStyle(
  color: string,
  active: boolean,
  open: boolean,
): React.CSSProperties {
  return {
    background: active ? `${color}33` : open ? "rgba(40,44,52,0.7)" : "rgba(20,22,28,0.6)",
    border: `1px solid ${active || open ? color : "rgba(207,210,214,0.2)"}`,
    borderRadius: 6,
    padding: "6px 4px",
    color: "#cfd2d6",
    fontFamily: "inherit",
    cursor: "pointer",
    textAlign: "center",
    transition: "background 0.3s ease",
  };
}

const pickerStyle: React.CSSProperties = {
  position: "absolute",
  bottom: 96,
  left: 18,
  width: 280,
  padding: 10,
  background: "rgba(15,17,22,0.95)",
  border: "1px solid rgba(207,210,214,0.25)",
  borderRadius: 8,
  color: "#cfd2d6",
  fontSize: 11,
  zIndex: 12,
};
