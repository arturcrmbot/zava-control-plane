import { useMemo, useState } from "react";
import { useComposition } from "../lib/useComposition";

/**
 * Section 3 — functional architecture diagram.
 *
 * Layout:
 *   - top band: agentic harness
 *   - left spine: identity, security, governance
 *   - middle column: skills row, MCPs row, real systems row
 *   - relationship lines between zones, highlighted on hover
 */

interface Agent {
  id: string;
  label: string;
  status: "alive" | "ghost";
  skills: string[];
}

interface ChipNode {
  id: string;
  label: string;
  links: string[];
}

const AGENTS: Agent[] = [
  { id: "ag-triage", label: "triage-agent", status: "alive", skills: ["sk-cv", "sk-shortlister"] },
  { id: "ag-offer", label: "offer-agent", status: "alive", skills: ["sk-offer", "sk-jurisdiction"] },
  { id: "ag-audit", label: "audit-agent", status: "ghost", skills: ["sk-audit"] },
];

const SKILLS: ChipNode[] = [
  { id: "sk-cv", label: "cv-crystalliser", links: ["mcp-ocr"] },
  { id: "sk-shortlister", label: "auto-shortlister", links: [] },
  { id: "sk-rag", label: "rag-classifier", links: ["mcp-policy", "mcp-claim"] },
  { id: "sk-offer", label: "offer-personaliser", links: [] },
  { id: "sk-audit", label: "audit-summariser", links: ["mcp-audit"] },
  { id: "sk-jurisdiction", label: "jurisdiction-router", links: ["mcp-policy"] },
];

const SKILL_OVERFLOW_DEFAULT = "… and others";

const MCPS: ChipNode[] = [
  { id: "mcp-policy", label: "policy_search", links: ["sys-di"] },
  { id: "mcp-ocr", label: "ocr_extract", links: ["sys-di"] },
  { id: "mcp-claim", label: "claim_lookup", links: ["sys-workday", "sys-concur"] },
  { id: "mcp-audit", label: "audit_query", links: [] },
];
const MCP_OVERFLOW_DEFAULT = "… and others";

const SYSTEMS: ChipNode[] = [
  { id: "sys-workday", label: "Workday", links: [] },
  { id: "sys-concur", label: "Concur", links: [] },
  { id: "sys-snow", label: "ServiceNow", links: [] },
  { id: "sys-greenhouse", label: "Greenhouse", links: [] },
  { id: "sys-graph", label: "Microsoft Graph", links: [] },
  { id: "sys-di", label: "Document Intelligence", links: [] },
];

const SPINE: never[] = [];

/**
 * Always-on guarantees — wraps the entire stack. Captions are written
 * for a business reader, not an engineer; each one names the concrete
 * thing the harness gives you that you don't have to build per-domain.
 */
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
  | { kind: "agent"; id: string }
  | { kind: "skill"; id: string }
  | { kind: "mcp"; id: string }
  | { kind: "system"; id: string }
  | { kind: "guarantee"; id: string }
  | null;

interface Highlight {
  agents: Set<string>;
  skills: Set<string>;
  mcps: Set<string>;
  systems: Set<string>;
  /** A guarantee is hovered — light up the whole stack to say "this applies everywhere". */
  glowAll: boolean;
  active: boolean;
}

function emptyHighlight(): Highlight {
  return {
    agents: new Set(),
    skills: new Set(),
    mcps: new Set(),
    systems: new Set(),
    glowAll: false,
    active: false,
  };
}

function highlightFor(hover: HoverState): Highlight {
  if (!hover) return emptyHighlight();
  const h = emptyHighlight();
  h.active = true;

  if (hover.kind === "agent") {
    h.agents.add(hover.id);
    const a = AGENTS.find((x) => x.id === hover.id);
    if (a) {
      a.skills.forEach((sid) => {
        h.skills.add(sid);
        const s = SKILLS.find((x) => x.id === sid);
        s?.links.forEach((mid) => {
          h.mcps.add(mid);
          const m = MCPS.find((x) => x.id === mid);
          m?.links.forEach((sysid) => h.systems.add(sysid));
        });
      });
    }
  } else if (hover.kind === "skill") {
    h.skills.add(hover.id);
    const a = AGENTS.find((x) => x.skills.includes(hover.id));
    if (a) h.agents.add(a.id);
    const s = SKILLS.find((x) => x.id === hover.id);
    s?.links.forEach((mid) => {
      h.mcps.add(mid);
      const m = MCPS.find((x) => x.id === mid);
      m?.links.forEach((sysid) => h.systems.add(sysid));
    });
  } else if (hover.kind === "mcp") {
    h.mcps.add(hover.id);
    SKILLS.forEach((s) => {
      if (s.links.includes(hover.id)) {
        h.skills.add(s.id);
        const a = AGENTS.find((x) => x.skills.includes(s.id));
        if (a) h.agents.add(a.id);
      }
    });
    const m = MCPS.find((x) => x.id === hover.id);
    m?.links.forEach((sysid) => h.systems.add(sysid));
  } else if (hover.kind === "system") {
    h.systems.add(hover.id);
    MCPS.forEach((m) => {
      if (m.links.includes(hover.id)) {
        h.mcps.add(m.id);
        SKILLS.forEach((s) => {
          if (s.links.includes(m.id)) {
            h.skills.add(s.id);
            const a = AGENTS.find((x) => x.skills.includes(s.id));
            if (a) h.agents.add(a.id);
          }
        });
      }
    });
  } else if (hover.kind === "guarantee") {
    h.glowAll = true;
  }
  return h;
}

export function ArchitectureDiagram() {
  const W = 1100;
  const H = 660;

  // Live counts power the overflow chips so the diagram doesn’t drift
  // every time a new skill or MCP gets cast. The drawn agents/skills/MCPs
  // themselves are intentionally illustrative — they’re a *shape* of the
  // architecture, not a manifest of every primitive.
  const { data: composition } = useComposition();
  const skillOverflowLabel = useMemo(() => {
    if (!composition) return SKILL_OVERFLOW_DEFAULT;
    const extra = composition.counts.skills - SKILLS.length;
    return extra > 0 ? `+ ${extra} more` : SKILL_OVERFLOW_DEFAULT;
  }, [composition]);
  const mcpOverflowLabel = useMemo(() => {
    if (!composition) return MCP_OVERFLOW_DEFAULT;
    const extra = composition.counts.mcps - MCPS.length;
    return extra > 0 ? `+ ${extra} more` : MCP_OVERFLOW_DEFAULT;
  }, [composition]);

  // No more side spine — the stack uses the full width, with the
  // always-on guarantees as a single band along the bottom.
  const stackX = 30;
  const stackW = W - stackX - 30;
  const harnessY = 30;
  const harnessH = 100;
  const skillsY = harnessY + harnessH + 28;
  const skillsH = 110;
  const mcpsY = skillsY + skillsH + 18;
  const mcpsH = 110;
  const systemsY = mcpsY + mcpsH + 18;
  const systemsH = 110;
  const guaranteesY = systemsY + systemsH + 24;
  const guaranteesH = 84;

  const [hover, setHover] = useState<HoverState>(null);
  const hl = useMemo(() => highlightFor(hover), [hover]);

  const skillX = (i: number) => stackX + 18 + i * 134 + 60;
  const mcpX = (i: number) => stackX + 18 + i * 148 + 65;
  const systemX = (i: number) => stackX + 18 + i * 152 + 40;
  const agentX = (i: number) => stackX + 18 + i * 154 + 65;

  const isActive = {
    agent: (id: string) => !hl.active || hl.glowAll || hl.agents.has(id),
    skill: (id: string) => !hl.active || hl.glowAll || hl.skills.has(id),
    mcp: (id: string) => !hl.active || hl.glowAll || hl.mcps.has(id),
    system: (id: string) => !hl.active || hl.glowAll || hl.systems.has(id),
  };

  const dimClass = (active: boolean) => (active ? "" : " arch__dim");
  const litClass = (active: boolean) => (hl.active && active ? " arch__lit" : "");

  // Lines connecting zones — drawn for every relationship; lit when the
  // current hover path passes through them.
  const lines: { x1: number; y1: number; x2: number; y2: number; lit: boolean; key: string }[] = [];
  AGENTS.forEach((a, ai) => {
    a.skills.forEach((sid) => {
      const skillIdx = SKILLS.findIndex((s) => s.id === sid);
      if (skillIdx < 0) return;
      const lit = hl.active && hl.agents.has(a.id) && hl.skills.has(sid);
      lines.push({
        x1: agentX(ai),
        y1: harnessY + 90,
        x2: skillX(skillIdx),
        y2: skillsY + 64,
        lit,
        key: `${a.id}-${sid}`,
      });
    });
  });
  SKILLS.forEach((s, si) => {
    s.links.forEach((mid) => {
      const mcpIdx = MCPS.findIndex((m) => m.id === mid);
      if (mcpIdx < 0) return;
      const lit = hl.active && hl.skills.has(s.id) && hl.mcps.has(mid);
      lines.push({
        x1: skillX(si),
        y1: skillsY + 92,
        x2: mcpX(mcpIdx),
        y2: mcpsY + 64,
        lit,
        key: `${s.id}-${mid}`,
      });
    });
  });
  MCPS.forEach((m, mi) => {
    m.links.forEach((sysid) => {
      const sysIdx = SYSTEMS.findIndex((s) => s.id === sysid);
      if (sysIdx < 0) return;
      const lit = hl.active && hl.mcps.has(m.id) && hl.systems.has(sysid);
      lines.push({
        x1: mcpX(mi),
        y1: mcpsY + 92,
        x2: systemX(sysIdx) + 30,
        y2: systemsY + 64,
        lit,
        key: `${m.id}-${sysid}`,
      });
    });
  });

  const captionFor = (state: HoverState): string => {
    if (!state) return "Hover any element to see what it composes and what depends on it.";
    if (state.kind === "agent") {
      const a = AGENTS.find((x) => x.id === state.id);
      const skills = a?.skills.map((sid) => SKILLS.find((s) => s.id === sid)?.label).filter(Boolean);
      return `${a?.label} loads ${skills?.length ?? 0} skill${(skills?.length ?? 0) === 1 ? "" : "s"}: ${skills?.join(", ")}`;
    }
    if (state.kind === "skill") {
      const s = SKILLS.find((x) => x.id === state.id);
      const mcps = s?.links.map((mid) => MCPS.find((m) => m.id === mid)?.label).filter(Boolean);
      return mcps && mcps.length > 0
        ? `${s?.label} allow-lists ${mcps.join(", ")}`
        : `${s?.label} runs without external tool calls`;
    }
    if (state.kind === "mcp") {
      const m = MCPS.find((x) => x.id === state.id);
      const sys = m?.links.map((sid) => SYSTEMS.find((s) => s.id === sid)?.label).filter(Boolean);
      return sys && sys.length > 0
        ? `${m?.label} fronts ${sys.join(", ")}`
        : `${m?.label} is local-only`;
    }
    if (state.kind === "system") {
      const s = SYSTEMS.find((x) => x.id === state.id);
      const fronting = MCPS.filter((m) => m.links.includes(state.id)).map((m) => m.label);
      return fronting.length > 0
        ? `${s?.label} reached through ${fronting.join(", ")}`
        : `${s?.label} (not currently fronted by an MCP in this sample)`;
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
          aria-label="Functional architecture: agentic harness on top, then skills, then MCPs, then your real systems. A row of always-on guarantees runs along the bottom and applies to every layer above. Hover any element to see relationships."
        >
          {/* (Governance moved to a single band along the bottom — see GUARANTEES). */}

          {/* Harness band */}
          <g>
            <rect
              x={stackX}
              y={harnessY}
              width={stackW}
              height={harnessH}
              className="arch__harness-band"
              rx={3}
            />
            <text x={stackX + 18} y={harnessY + 26} className="arch__zone-label">
              AGENTIC HARNESS
            </text>
            <text x={stackX + 18} y={harnessY + 50} className="arch__zone-sub">
              spawn an agent, give it skills + MCPs, tear it down when done
            </text>

            {AGENTS.map((a, i) => {
              const x = stackX + 18 + i * 154;
              const y = harnessY + 64;
              const active = isActive.agent(a.id);
              const lit = hl.active && hl.agents.has(a.id);
              return (
                <g
                  key={a.id}
                  transform={`translate(${x}, ${y})`}
                  onMouseEnter={() => setHover({ kind: "agent", id: a.id })}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    width={140}
                    height={26}
                    rx={3}
                    className={`arch__agent arch__agent--${a.status}${lit ? " arch__agent--lit" : ""}${dimClass(active)}`}
                  />
                  <text
                    x={70}
                    y={17}
                    textAnchor="middle"
                    className={`arch__agent-label${dimClass(active)}`}
                  >
                    {a.label}
                  </text>
                  <text
                    x={70}
                    y={42}
                    textAnchor="middle"
                    className={`arch__agent-status arch__agent-status--${a.status}${dimClass(active)}`}
                  >
                    {a.status}
                  </text>
                </g>
              );
            })}
          </g>

          {/* Lines */}
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
            <rect
              x={stackX}
              y={skillsY}
              width={stackW}
              height={skillsH}
              className="arch__row arch__row--skills"
              rx={3}
            />
            <text x={stackX + 18} y={skillsY + 26} className="arch__zone-label">
              SKILLS
            </text>
            <text x={stackX + 18} y={skillsY + 50} className="arch__zone-sub">
              modular units of know-how, governed centrally
            </text>
            {SKILLS.map((s, i) => {
              const active = isActive.skill(s.id);
              const lit = hl.active && hl.skills.has(s.id);
              return (
                <g
                  key={s.id}
                  transform={`translate(${stackX + 18 + i * 134}, ${skillsY + 64})`}
                  onMouseEnter={() => setHover({ kind: "skill", id: s.id })}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    width={128}
                    height={28}
                    rx={3}
                    className={`arch__chip arch__chip--skill${lit ? " arch__chip--lit" : ""}${dimClass(active)}`}
                  />
                  <text
                    x={64}
                    y={18}
                    textAnchor="middle"
                    className={`arch__chip-label${dimClass(active)}`}
                  >
                    {s.label}
                  </text>
                </g>
              );
            })}
            <g transform={`translate(${stackX + 18 + SKILLS.length * 134}, ${skillsY + 64})`}>
              <rect width={96} height={28} rx={3} className="arch__chip arch__chip--overflow" />
              <text x={48} y={18} textAnchor="middle" className="arch__chip-label arch__chip-label--mute">
                {skillOverflowLabel}
              </text>
            </g>
          </g>

          {/* MCPs row */}
          <g>
            <rect
              x={stackX}
              y={mcpsY}
              width={stackW}
              height={mcpsH}
              className="arch__row arch__row--mcps"
              rx={3}
            />
            <text x={stackX + 18} y={mcpsY + 26} className="arch__zone-label">
              MCPs
            </text>
            <text x={stackX + 18} y={mcpsY + 50} className="arch__zone-sub">
              federated capability layer over your real systems
            </text>
            {MCPS.map((m, i) => {
              const active = isActive.mcp(m.id);
              const lit = hl.active && hl.mcps.has(m.id);
              return (
                <g
                  key={m.id}
                  transform={`translate(${stackX + 18 + i * 148}, ${mcpsY + 64})`}
                  onMouseEnter={() => setHover({ kind: "mcp", id: m.id })}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    width={138}
                    height={28}
                    rx={3}
                    className={`arch__chip arch__chip--mcp${lit ? " arch__chip--lit" : ""}${dimClass(active)}`}
                  />
                  <text
                    x={69}
                    y={18}
                    textAnchor="middle"
                    className={`arch__chip-label${dimClass(active)}`}
                  >
                    {m.label}
                  </text>
                </g>
              );
            })}
            <g transform={`translate(${stackX + 18 + MCPS.length * 148}, ${mcpsY + 64})`}>
              <rect width={96} height={28} rx={3} className="arch__chip arch__chip--overflow" />
              <text x={48} y={18} textAnchor="middle" className="arch__chip-label arch__chip-label--mute">
                {mcpOverflowLabel}
              </text>
            </g>
          </g>

          {/* Systems row */}
          <g>
            <rect
              x={stackX}
              y={systemsY}
              width={stackW}
              height={systemsH}
              className="arch__row arch__row--systems"
              rx={3}
            />
            <text x={stackX + 18} y={systemsY + 26} className="arch__zone-label">
              YOUR SYSTEMS
            </text>
            <text x={stackX + 18} y={systemsY + 50} className="arch__zone-sub">
              where the work actually lives — agents borrow them through MCPs
            </text>
            {SYSTEMS.map((s, i) => {
              const active = isActive.system(s.id);
              const lit = hl.active && hl.systems.has(s.id);
              return (
                <g
                  key={s.id}
                  transform={`translate(${stackX + 18 + i * 152}, ${systemsY + 64})`}
                  onMouseEnter={() => setHover({ kind: "system", id: s.id })}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    width={140}
                    height={28}
                    rx={3}
                    className={`arch__chip arch__chip--system${lit ? " arch__chip--lit" : ""}${dimClass(active)}`}
                  />
                  <text
                    x={70}
                    y={18}
                    textAnchor="middle"
                    className={`arch__chip-label${dimClass(active)}`}
                  >
                    {s.label}
                  </text>
                </g>
              );
            })}
          </g>

          {/* Always-on guarantees band — wraps the whole stack. */}
          <g>
            <rect
              x={stackX}
              y={guaranteesY}
              width={stackW}
              height={guaranteesH}
              className={`arch__guarantees-band${hl.glowAll ? " arch__guarantees-band--glow" : ""}`}
              rx={3}
            />
            <text x={stackX + 18} y={guaranteesY + 26} className="arch__zone-label">
              ALWAYS‑ON GUARANTEES
            </text>
            <text x={stackX + 18} y={guaranteesY + 46} className="arch__zone-sub">
              built once into the harness — carried into every domain after
            </text>
            {GUARANTEES.map((g, i) => {
              const colW = (stackW - 36) / GUARANTEES.length;
              const x = stackX + 18 + i * colW;
              const y = guaranteesY + 56;
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
