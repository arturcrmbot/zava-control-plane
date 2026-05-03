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

const SPINE = [
  { id: "sp-entra", label: "Entra Agent ID", governs: "harness" },
  { id: "sp-365", label: "Agent 365", governs: "harness" },
  { id: "sp-audit", label: "Audit ledger", governs: "all" },
  { id: "sp-hooks", label: "Hooks on sends", governs: "skills" },
  { id: "sp-validators", label: "Validators", governs: "skills" },
  { id: "sp-policy", label: "Policy-driven", governs: "skills" },
  { id: "sp-otel", label: "OTEL spans", governs: "all" },
  { id: "sp-cost", label: "Cost attribution", governs: "all" },
];

type HoverState =
  | { kind: "agent"; id: string }
  | { kind: "skill"; id: string }
  | { kind: "mcp"; id: string }
  | { kind: "system"; id: string }
  | { kind: "spine"; id: string }
  | null;

interface Highlight {
  agents: Set<string>;
  skills: Set<string>;
  mcps: Set<string>;
  systems: Set<string>;
  spineGroup: "harness" | "skills" | "mcps" | "systems" | "all" | null;
  active: boolean;
}

function emptyHighlight(): Highlight {
  return {
    agents: new Set(),
    skills: new Set(),
    mcps: new Set(),
    systems: new Set(),
    spineGroup: null,
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
  } else if (hover.kind === "spine") {
    const item = SPINE.find((x) => x.id === hover.id);
    if (item) h.spineGroup = item.governs as Highlight["spineGroup"];
  }
  return h;
}

export function ArchitectureDiagram() {
  const W = 1100;
  const H = 540;

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

  const spineX = 30;
  const spineW = 110;
  const harnessY = 30;
  const harnessH = 100;
  const stackX = spineX + spineW + 28;
  const stackW = W - stackX - 30;
  const skillsY = harnessY + harnessH + 28;
  const skillsH = 110;
  const mcpsY = skillsY + skillsH + 18;
  const mcpsH = 110;
  const systemsY = mcpsY + mcpsH + 18;
  const systemsH = 110;

  const [hover, setHover] = useState<HoverState>(null);
  const hl = useMemo(() => highlightFor(hover), [hover]);

  const skillX = (i: number) => stackX + 18 + i * 116 + 55;
  const mcpX = (i: number) => stackX + 18 + i * 128 + 60;
  const systemX = (i: number) => stackX + 18 + i * 130 + 40;
  const agentX = (i: number) => stackX + 18 + i * 134 + 60;

  const isActive = {
    agent: (id: string) => !hl.active || hl.agents.has(id),
    skill: (id: string) => !hl.active || hl.skills.has(id),
    mcp: (id: string) => !hl.active || hl.mcps.has(id),
    system: (id: string) => !hl.active || hl.systems.has(id),
    spineRow: (group: string) => {
      if (!hl.active) return true;
      if (hl.spineGroup === "all") return true;
      if (hl.spineGroup === group) return true;
      return false;
    },
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
    if (state.kind === "spine") {
      const item = SPINE.find((x) => x.id === state.id);
      const map: Record<string, string> = {
        harness: "the agentic harness",
        skills: "every skill",
        mcps: "every MCP",
        systems: "every system call",
        all: "every layer",
      };
      return `${item?.label} governs ${map[item?.governs ?? "all"]}`;
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
          aria-label="Functional architecture: agentic harness on top, governance spine on the left, skills and MCPs and real systems stacked beneath. Hover any element to see relationships."
        >
          {/* Spine */}
          <g>
            <rect
              x={spineX}
              y={harnessY}
              width={spineW}
              height={H - harnessY - 30}
              className="arch__spine"
              rx={3}
            />
            <text x={spineX + 16} y={harnessY + 26} className="arch__zone-label">
              GOVERNANCE
            </text>
            <text x={spineX + 16} y={harnessY + 50} className="arch__zone-sub">
              identity · audit
            </text>
            {SPINE.map((item, i) => {
              const yPos = 110 + i * 44;
              const isHovered = hover?.kind === "spine" && hover.id === item.id;
              return (
                <g
                  key={item.id}
                  onMouseEnter={() => setHover({ kind: "spine", id: item.id })}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    x={spineX + 6}
                    y={yPos - 14}
                    width={spineW - 12}
                    height={20}
                    rx={2}
                    className={`arch__spine-chip${isHovered ? " arch__spine-chip--hover" : ""}`}
                  />
                  <text x={spineX + 16} y={yPos} className="arch__spine-item">
                    {item.label}
                  </text>
                </g>
              );
            })}
          </g>

          {/* Harness band */}
          <g>
            <rect
              x={stackX}
              y={harnessY}
              width={stackW}
              height={harnessH}
              className={`arch__harness-band${litClass(isActive.spineRow("harness"))}${dimClass(isActive.spineRow("harness"))}`}
              rx={3}
            />
            <text x={stackX + 18} y={harnessY + 26} className="arch__zone-label">
              AGENTIC HARNESS
            </text>
            <text x={stackX + 18} y={harnessY + 50} className="arch__zone-sub">
              spawn an agent, give it skills + MCPs, tear it down when done
            </text>

            {AGENTS.map((a, i) => {
              const x = stackX + 18 + i * 134;
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
                    width={120}
                    height={26}
                    rx={3}
                    className={`arch__agent arch__agent--${a.status}${lit ? " arch__agent--lit" : ""}${dimClass(active)}`}
                  />
                  <text
                    x={60}
                    y={17}
                    textAnchor="middle"
                    className={`arch__agent-label${dimClass(active)}`}
                  >
                    {a.label}
                  </text>
                  <text
                    x={60}
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
              className={`arch__row arch__row--skills${dimClass(isActive.spineRow("skills"))}`}
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
                  transform={`translate(${stackX + 18 + i * 116}, ${skillsY + 64})`}
                  onMouseEnter={() => setHover({ kind: "skill", id: s.id })}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    width={110}
                    height={28}
                    rx={3}
                    className={`arch__chip arch__chip--skill${lit ? " arch__chip--lit" : ""}${dimClass(active)}`}
                  />
                  <text
                    x={55}
                    y={18}
                    textAnchor="middle"
                    className={`arch__chip-label${dimClass(active)}`}
                  >
                    {s.label}
                  </text>
                </g>
              );
            })}
            <g transform={`translate(${stackX + 18 + SKILLS.length * 116}, ${skillsY + 64})`}>
              <rect width={84} height={28} rx={3} className="arch__chip arch__chip--overflow" />
              <text x={42} y={18} textAnchor="middle" className="arch__chip-label arch__chip-label--mute">
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
              className={`arch__row arch__row--mcps${dimClass(isActive.spineRow("mcps"))}`}
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
                  transform={`translate(${stackX + 18 + i * 128}, ${mcpsY + 64})`}
                  onMouseEnter={() => setHover({ kind: "mcp", id: m.id })}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    width={120}
                    height={28}
                    rx={3}
                    className={`arch__chip arch__chip--mcp${lit ? " arch__chip--lit" : ""}${dimClass(active)}`}
                  />
                  <text
                    x={60}
                    y={18}
                    textAnchor="middle"
                    className={`arch__chip-label${dimClass(active)}`}
                  >
                    {m.label}
                  </text>
                </g>
              );
            })}
            <g transform={`translate(${stackX + 18 + MCPS.length * 128}, ${mcpsY + 64})`}>
              <rect width={84} height={28} rx={3} className="arch__chip arch__chip--overflow" />
              <text x={42} y={18} textAnchor="middle" className="arch__chip-label arch__chip-label--mute">
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
              className={`arch__row arch__row--systems${dimClass(isActive.spineRow("systems"))}`}
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
                  transform={`translate(${stackX + 18 + i * 130}, ${systemsY + 64})`}
                  onMouseEnter={() => setHover({ kind: "system", id: s.id })}
                  style={{ cursor: "pointer" }}
                >
                  <rect
                    width={120}
                    height={28}
                    rx={3}
                    className={`arch__chip arch__chip--system${lit ? " arch__chip--lit" : ""}${dimClass(active)}`}
                  />
                  <text
                    x={60}
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
        </svg>
      </div>

      <div className={`arch__caption${hover ? " arch__caption--active" : ""}`}>
        {captionFor(hover)}
      </div>
    </div>
  );
}
