import { useMemo, useState } from "react";
import { useComposition } from "../lib/useComposition";
import type { Domain, Skill, Mcp } from "../lib/types";

/**
 * Section 3 — functional architecture diagram.
 *
 * Fully data-driven: every node is read from /api/blueprint/composition.
 *
 * Layout (top → bottom):
 *   - Domains row      : every live domain (ramped, recordable). "Agentic
 *                        harness" used to be a hardcoded list of three
 *                        invented agent identities — replaced with the
 *                        actual domains the harness runs today.
 *   - Skills row       : up to N skills directly (rest collapse into a
 *                        "+ N more" chip). The 8 most-shared skills bubble
 *                        to the front so the compounding case is visible.
 *   - MCPs row         : same treatment, ranked by skills-allow-listing
 *                        count (hub MCPs first).
 *   - Always-on band   : guarantees that wrap every domain.
 *
 * Hover any chip and the related layers light up. Edges between layers
 * are drawn from the actual skill `allowed_tools` and domain `skills`
 * arrays — no static link maps.
 */

const VISIBLE_DOMAINS = 12;
const VISIBLE_SKILLS = 10;
const VISIBLE_MCPS = 12;

interface Guarantee {
  id: string;
  label: string;
  caption: string;
}

const GUARANTEES: Guarantee[] = [
  {
    id: "g-identity",
    label: "Identity on every action",
    caption:
      "Each agent runs under its own Entra Agent ID. Every call into Workday, Concur, ServiceNow, or any other system is signed by that identity — so the audit trail names the agent, not a shared service account.",
  },
  {
    id: "g-validator",
    label: "Validator before every send",
    caption:
      "Outputs are checked against policy before they leave the harness. A bad message, a non‑compliant offer, an unapproved expense — blocked at the boundary, never sent. No after‑the‑fact patching.",
  },
  {
    id: "g-audit",
    label: "Audit ledger on every step",
    caption:
      "Who did what, why, when, on whose behalf, and what it cost — written to an immutable ledger automatically. Reviewers don't reconstruct it from logs; it's already there.",
  },
  {
    id: "g-policy",
    label: "Policy as data, not code",
    caption:
      "Approval thresholds, jurisdiction routing, allow‑listed tools — defined in YAML. Compliance edits the rules; no engineer needed, no redeploy. Validators re‑read the policy on every request.",
  },
];

type HoverState =
  | { kind: "domain"; id: string }
  | { kind: "skill"; id: string }
  | { kind: "mcp"; id: string }
  | { kind: "guarantee"; id: string }
  | null;

interface Highlight {
  domains: Set<string>;
  skills: Set<string>;
  mcps: Set<string>;
  glowAll: boolean;
  active: boolean;
}

function emptyHighlight(): Highlight {
  return {
    domains: new Set(),
    skills: new Set(),
    mcps: new Set(),
    glowAll: false,
    active: false,
  };
}

interface Indices {
  skillByName: Map<string, Skill>;
  mcpByName: Map<string, Mcp>;
  domainByName: Map<string, Domain>;
}

function highlightFor(
  hover: HoverState,
  ix: Indices,
): Highlight {
  if (!hover) return emptyHighlight();
  const h = emptyHighlight();
  h.active = true;

  if (hover.kind === "domain") {
    const d = ix.domainByName.get(hover.id);
    if (!d) return h;
    h.domains.add(d.name);
    d.skills.forEach((sn) => h.skills.add(sn));
    d.tools.forEach((tn) => h.mcps.add(tn));
  } else if (hover.kind === "skill") {
    const s = ix.skillByName.get(hover.id);
    if (!s) return h;
    h.skills.add(s.name);
    s.domains.forEach((dn) => h.domains.add(dn));
    s.allowed_tools.forEach((tn) => h.mcps.add(tn));
  } else if (hover.kind === "mcp") {
    const m = ix.mcpByName.get(hover.id);
    if (!m) return h;
    h.mcps.add(m.name);
    m.used_by_skills.forEach((sn) => {
      h.skills.add(sn);
      const s = ix.skillByName.get(sn);
      s?.domains.forEach((dn) => h.domains.add(dn));
    });
  } else if (hover.kind === "guarantee") {
    h.glowAll = true;
  }
  return h;
}

export function ArchitectureDiagram() {
  const { data: composition, loading, error } = useComposition();
  const [hover, setHover] = useState<HoverState>(null);

  const ix = useMemo<Indices>(() => {
    const skillByName = new Map<string, Skill>();
    const mcpByName = new Map<string, Mcp>();
    const domainByName = new Map<string, Domain>();
    composition?.skills.forEach((s) => skillByName.set(s.name, s));
    composition?.mcps.forEach((m) => mcpByName.set(m.name, m));
    composition?.domains.forEach((d) => domainByName.set(d.name, d));
    return { skillByName, mcpByName, domainByName };
  }, [composition]);

  // Rank skills + MCPs by reuse so the "compounding" story leads.
  const rankedDomains = useMemo<Domain[]>(() => {
    if (!composition) return [];
    return composition.domains.filter((d) => d.status === "live");
  }, [composition]);

  const rankedSkills = useMemo<Skill[]>(() => {
    if (!composition) return [];
    return [...composition.skills].sort((a, b) => {
      const da = a.domains.length;
      const db = b.domains.length;
      if (db !== da) return db - da;
      return a.name.localeCompare(b.name);
    });
  }, [composition]);

  const rankedMcps = useMemo<Mcp[]>(() => {
    if (!composition) return [];
    return [...composition.mcps].sort((a, b) => {
      const da = a.used_by_skills.length;
      const db = b.used_by_skills.length;
      if (db !== da) return db - da;
      return a.name.localeCompare(b.name);
    });
  }, [composition]);

  const visibleDomains = rankedDomains.slice(0, VISIBLE_DOMAINS);
  const visibleSkills = rankedSkills.slice(0, VISIBLE_SKILLS);
  const visibleMcps = rankedMcps.slice(0, VISIBLE_MCPS);

  const hl = useMemo(() => highlightFor(hover, ix), [hover, ix]);

  // Dimensions. Domains row is taller (3 lines per chip). Other rows are
  // single-line chips. Edges are drawn from chip centres.
  const W = 1180;
  const stackX = 30;
  const stackW = W - stackX - 30;

  const domainsY = 30;
  const domainsH = 130;
  const skillsY = domainsY + domainsH + 28;
  const skillsH = 100;
  const mcpsY = skillsY + skillsH + 18;
  const mcpsH = 100;
  const guaranteesY = mcpsY + mcpsH + 24;
  const guaranteesH = 100;
  const H = guaranteesY + guaranteesH + 30;

  const innerX = stackX + 18;
  const innerW = stackW - 36;

  const domainColW = visibleDomains.length > 0 ? innerW / visibleDomains.length : innerW;
  const skillColW = visibleSkills.length > 0 ? innerW / (visibleSkills.length + 1) : innerW;
  const mcpColW = visibleMcps.length > 0 ? innerW / (visibleMcps.length + 1) : innerW;

  const domainXCentre = (i: number) => innerX + (i + 0.5) * domainColW;
  const skillXCentre = (i: number) => innerX + (i + 0.5) * skillColW;
  const mcpXCentre = (i: number) => innerX + (i + 0.5) * mcpColW;

  const isActiveDomain = (id: string) => !hl.active || hl.glowAll || hl.domains.has(id);
  const isActiveSkill = (id: string) => !hl.active || hl.glowAll || hl.skills.has(id);
  const isActiveMcp = (id: string) => !hl.active || hl.glowAll || hl.mcps.has(id);

  const dimClass = (active: boolean) => (active ? "" : " arch__dim");

  // Edges, computed from the live composition.
  type Edge = { x1: number; y1: number; x2: number; y2: number; lit: boolean; key: string };
  const lines: Edge[] = [];
  visibleDomains.forEach((d, di) => {
    d.skills.forEach((sn) => {
      const skillIdx = visibleSkills.findIndex((s) => s.name === sn);
      if (skillIdx < 0) return;
      const lit = hl.active && hl.domains.has(d.name) && hl.skills.has(sn);
      lines.push({
        x1: domainXCentre(di),
        y1: domainsY + domainsH - 14,
        x2: skillXCentre(skillIdx),
        y2: skillsY + 64,
        lit,
        key: `d-${d.name}-${sn}`,
      });
    });
  });
  visibleSkills.forEach((s, si) => {
    s.allowed_tools.forEach((tn) => {
      const mcpIdx = visibleMcps.findIndex((m) => m.name === tn);
      if (mcpIdx < 0) return;
      const lit = hl.active && hl.skills.has(s.name) && hl.mcps.has(tn);
      lines.push({
        x1: skillXCentre(si),
        y1: skillsY + 92,
        x2: mcpXCentre(mcpIdx),
        y2: mcpsY + 64,
        lit,
        key: `s-${s.name}-${tn}`,
      });
    });
  });

  const captionFor = (state: HoverState): string => {
    if (!state) {
      if (loading) return "Loading composition...";
      if (error) return `composition unavailable (${error}) — showing empty layout.`;
      const c = composition?.counts;
      if (!c) return "Hover any chip to see what it composes and what depends on it.";
      return (
        `${c.domains_live} domains · ${c.skills} skills · ${c.mcps} MCP tools — ` +
        `each generated domain reuses skills + tools that came from earlier ones. ` +
        `Hover any chip to see the chain.`
      );
    }
    if (state.kind === "domain") {
      const d = ix.domainByName.get(state.id);
      if (!d) return "";
      return `${d.name} composes ${d.skills.length} skill${d.skills.length === 1 ? "" : "s"} and ${d.tools.length} MCP${d.tools.length === 1 ? "" : "s"}.`;
    }
    if (state.kind === "skill") {
      const s = ix.skillByName.get(state.id);
      if (!s) return "";
      const reuse = s.domains.length > 1 ? ` · reused by ${s.domains.length} domains` : "";
      return `${s.name} → ${s.allowed_tools.join(", ") || "no MCP tools"}${reuse}`;
    }
    if (state.kind === "mcp") {
      const m = ix.mcpByName.get(state.id);
      if (!m) return "";
      const ops = m.operations && m.operations.length > 1 ? ` (${m.operations.length} operations)` : "";
      const callers = m.used_by_skills.length === 0 ? "no skills yet" : `${m.used_by_skills.length} skill${m.used_by_skills.length === 1 ? "" : "s"}`;
      return `${m.name}${ops} ← ${callers}`;
    }
    if (state.kind === "guarantee") {
      const g = GUARANTEES.find((x) => x.id === state.id);
      return g ? g.caption : "";
    }
    return "";
  };

  return (
    <div className="arch__wrapper" onMouseLeave={() => setHover(null)}>
      <div className="arch__scroll">
        <svg
          className="arch"
          viewBox={`0 0 ${W} ${H}`}
          width={W}
          height={H}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label="Functional architecture: live domains on top, then their skills, then the MCP tools those skills allow-list. A row of always-on guarantees runs along the bottom and applies to every domain. Hover any chip to see relationships."
        >
          {/* Domains row */}
          <g>
            <rect x={stackX} y={domainsY} width={stackW} height={domainsH} className="arch__harness-band" rx={3} />
            <text x={innerX} y={domainsY + 26} className="arch__zone-label">DOMAINS</text>
            <text x={innerX} y={domainsY + 50} className="arch__zone-sub">
              every domain is its own ephemeral agent harness — same substrate, different brief
            </text>
            {visibleDomains.map((d, i) => {
              const x = innerX + i * domainColW + 4;
              const y = domainsY + 64;
              const active = isActiveDomain(d.name);
              const lit = hl.active && hl.domains.has(d.name);
              return (
                <g
                  key={d.name}
                  transform={`translate(${x}, ${y})`}
                  onMouseEnter={() => setHover({ kind: "domain", id: d.name })}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    width={domainColW - 8}
                    height={56}
                    rx={3}
                    className={`arch__agent arch__agent--alive${lit ? " arch__agent--lit" : ""}${dimClass(active)}`}
                  />
                  <text
                    x={(domainColW - 8) / 2}
                    y={22}
                    textAnchor="middle"
                    className={`arch__agent-label${dimClass(active)}`}
                  >
                    {d.name}
                  </text>
                  <text
                    x={(domainColW - 8) / 2}
                    y={42}
                    textAnchor="middle"
                    className={`arch__agent-status arch__agent-status--alive${dimClass(active)}`}
                  >
                    {d.skills.length} skill{d.skills.length === 1 ? "" : "s"} · {d.tools.length} MCP{d.tools.length === 1 ? "" : "s"}
                  </text>
                </g>
              );
            })}
          </g>

          {/* Edges */}
          {lines.map((l) => (
            <line
              key={l.key}
              x1={l.x1}
              y1={l.y1}
              x2={l.x2}
              y2={l.y2}
              className={`arch__line${l.lit ? " arch__line--lit" : ""}`}
            />
          ))}

          {/* Skills row */}
          <g>
            <rect x={stackX} y={skillsY} width={stackW} height={skillsH} className="arch__row arch__row--skills" rx={3} />
            <text x={innerX} y={skillsY + 26} className="arch__zone-label">SKILLS</text>
            <text x={innerX} y={skillsY + 50} className="arch__zone-sub">
              modular units of know-how, ranked by reuse across domains
            </text>
            {visibleSkills.map((s, i) => {
              const cx = skillXCentre(i);
              const w = Math.max(80, skillColW - 12);
              const x = cx - w / 2;
              const y = skillsY + 64;
              const active = isActiveSkill(s.name);
              const lit = hl.active && hl.skills.has(s.name);
              return (
                <g
                  key={s.name}
                  transform={`translate(${x}, ${y})`}
                  onMouseEnter={() => setHover({ kind: "skill", id: s.name })}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    width={w}
                    height={28}
                    rx={3}
                    className={`arch__chip arch__chip--skill${lit ? " arch__chip--lit" : ""}${dimClass(active)}`}
                  />
                  <text
                    x={w / 2}
                    y={18}
                    textAnchor="middle"
                    className={`arch__chip-label${dimClass(active)}`}
                  >
                    {s.name}
                  </text>
                </g>
              );
            })}
            {composition && composition.skills.length > VISIBLE_SKILLS && (
              <g transform={`translate(${skillXCentre(visibleSkills.length) - 40}, ${skillsY + 64})`}>
                <rect width={80} height={28} rx={3} className="arch__chip arch__chip--overflow" />
                <text x={40} y={18} textAnchor="middle" className="arch__chip-label arch__chip-label--mute">
                  + {composition.skills.length - VISIBLE_SKILLS} more
                </text>
              </g>
            )}
          </g>

          {/* MCPs row */}
          <g>
            <rect x={stackX} y={mcpsY} width={stackW} height={mcpsH} className="arch__row arch__row--mcps" rx={3} />
            <text x={innerX} y={mcpsY + 26} className="arch__zone-label">MCP TOOLS</text>
            <text x={innerX} y={mcpsY + 50} className="arch__zone-sub">
              federated capability layer over your real systems — hub MCPs first
            </text>
            {visibleMcps.map((m, i) => {
              const cx = mcpXCentre(i);
              const w = Math.max(80, mcpColW - 12);
              const x = cx - w / 2;
              const y = mcpsY + 64;
              const active = isActiveMcp(m.name);
              const lit = hl.active && hl.mcps.has(m.name);
              return (
                <g
                  key={m.name}
                  transform={`translate(${x}, ${y})`}
                  onMouseEnter={() => setHover({ kind: "mcp", id: m.name })}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    width={w}
                    height={28}
                    rx={3}
                    className={`arch__chip arch__chip--mcp${lit ? " arch__chip--lit" : ""}${dimClass(active)}`}
                  />
                  <text
                    x={w / 2}
                    y={18}
                    textAnchor="middle"
                    className={`arch__chip-label${dimClass(active)}`}
                  >
                    {m.name}
                  </text>
                </g>
              );
            })}
            {composition && composition.mcps.length > VISIBLE_MCPS && (
              <g transform={`translate(${mcpXCentre(visibleMcps.length) - 40}, ${mcpsY + 64})`}>
                <rect width={80} height={28} rx={3} className="arch__chip arch__chip--overflow" />
                <text x={40} y={18} textAnchor="middle" className="arch__chip-label arch__chip-label--mute">
                  + {composition.mcps.length - VISIBLE_MCPS} more
                </text>
              </g>
            )}
          </g>

          {/* Always-on guarantees */}
          <g>
            <rect
              x={stackX}
              y={guaranteesY}
              width={stackW}
              height={guaranteesH}
              className={`arch__guarantees-band${hl.glowAll ? " arch__guarantees-band--glow" : ""}`}
              rx={3}
            />
            <text x={innerX} y={guaranteesY + 26} className="arch__zone-label">
              ALWAYS‑ON GUARANTEES
            </text>
            <text x={innerX} y={guaranteesY + 46} className="arch__zone-sub">
              built once into the harness — carried into every domain after
            </text>
            {GUARANTEES.map((g, i) => {
              const colW = innerW / GUARANTEES.length;
              const x = innerX + i * colW;
              const y = guaranteesY + 76;
              const isHovered = hover?.kind === "guarantee" && hover.id === g.id;
              return (
                <g
                  key={g.id}
                  onMouseEnter={() => setHover({ kind: "guarantee", id: g.id })}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    x={x}
                    y={y - 14}
                    width={colW - 12}
                    height={20}
                    rx={2}
                    className={`arch__guarantee-chip${isHovered ? " arch__guarantee-chip--hover" : ""}`}
                  />
                  <text
                    x={x + (colW - 12) / 2}
                    y={y}
                    textAnchor="middle"
                    className="arch__guarantee-label"
                  >
                    {g.label}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      <div className={`arch__caption${hover ? " arch__caption--active" : ""}`}>
        {captionFor(hover)}
      </div>
    </div>
  );
}
