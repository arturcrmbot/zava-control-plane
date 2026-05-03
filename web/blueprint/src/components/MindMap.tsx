import { useEffect, useMemo, useRef, useState } from "react";
import type { CompositionTree, ObservatoryEvent } from "../lib/types";

/**
 * Live mind-map for the observatory section. Single active domain at centre.
 * Drawn as concentric rings: domain → phases → skills → MCP tools.
 *
 * Two reverse mappings come in from the composition tree, not from
 * in-component constants:
 *
 *   - `composition.workflow_types["hiring"] === "Hiring"`
 *     The mind-map can label any new domain the manifest declares without
 *     a code change here.
 *
 *   - `composition.phase_aliases["cv-crystalliser"] === "Triage"`
 *     New skills get a phase label by appearing in DOMAINS in the
 *     inventory; nothing else changes.
 */

interface Props {
  /** Stream of normalised observatory events, newest first. */
  events: ObservatoryEvent[];
  /** Live status of the SSE connection. Used for the resting visual. */
  status: "watching" | "connecting" | "offline";
  /**
   * Composition tree from /api/blueprint/composition. Optional — when
   * absent the mind-map still renders, it just can't label phases or
   * derive a domain name from the workflow_id prefix fallback.
   */
  composition?: CompositionTree | null;
}

type ActiveSkill = {
  name: string;
  /** Timestamp it last fired, in ms. */
  lastFiredMs: number;
  /** Deterministic angle around the current phase node. */
  angle: number;
};

type ActiveTool = {
  name: string;
  lastFiredMs: number;
};

type Traversal = {
  id: string;
  fromSkill: string;
  toTool: string;
  blocked: boolean;
  startMs: number;
};

type DomainState = {
  name: string;
  workflowId: string | null;
  currentPhase: string | null;
  /** Order of phases as they have been observed; we do not pre-declare them. */
  phasesSeen: string[];
  activeSkills: Map<string, ActiveSkill>;
  activeTools: Map<string, ActiveTool>;
  traversals: Traversal[];
  status: "live" | "completed" | "blocked";
};

const SKILL_FADE_MS = 2400;
const TOOL_FADE_MS = 2400;
const TRAVERSAL_DURATION_MS = 1600;

function _emptyDomain(name: string): DomainState {
  return {
    name,
    workflowId: null,
    currentPhase: null,
    phasesSeen: [],
    activeSkills: new Map(),
    activeTools: new Map(),
    traversals: [],
    status: "live",
  };
}

export function MindMap({ events, status, composition }: Props) {
  const [activeDomain, setActiveDomain] = useState<DomainState | null>(null);
  const seenEventsRef = useRef<Set<number>>(new Set());
  const [, force] = useState(0);

  // Reverse lookups derived from the composition tree.
  const phaseAliases = composition?.phase_aliases ?? {};
  const _domainFromEvent = (e: ObservatoryEvent): string | null => {
    if (e.domain) return e.domain;
    return null;
  };

  // Watch the head of the events list for new events; fold them into the
  // active domain state. Events older than what we've seen are ignored.
  useEffect(() => {
    if (events.length === 0) return;
    const head = events[0];
    if (seenEventsRef.current.has(head.ts)) return;
    seenEventsRef.current.add(head.ts);

    const now = Date.now();
    setActiveDomain((current) => {
      let next = current;
      const eventDomain = _domainFromEvent(head);
      // Switch active domain on workflow.started, OR on first sight of any
      // event that names a domain when there is no current domain yet.
      if (head.type === "workflow.started" || head.type === "durable.workflow.started") {
        if (eventDomain) {
          next = _emptyDomain(eventDomain);
          next.workflowId = head.workflow_id;
        }
      } else if (!next && eventDomain) {
        next = _emptyDomain(eventDomain);
        next.workflowId = head.workflow_id;
      }
      if (!next) return current;

      // Phase derivation from skill name, sourced from the manifest.
      const phase = head.skill ? (phaseAliases[head.skill] ?? null) : null;
      if (phase) {
        if (!next.phasesSeen.includes(phase)) next.phasesSeen.push(phase);
        next.currentPhase = phase;
      }

      // Update skill activity.
      if (head.skill && (
        head.type === "durable.step.started" ||
        head.type === "durable.step.completed" ||
        head.type === "durable.executor.invoked" ||
        head.type === "agent.completed"
      )) {
        const angle = (next.activeSkills.size * 360) / 6 + 30; // staggered
        const existing = next.activeSkills.get(head.skill);
        next.activeSkills.set(head.skill, {
          name: head.skill,
          lastFiredMs: now,
          angle: existing?.angle ?? angle,
        });
      }

      // Update tool activity + traversal animation.
      if (head.tool) {
        next.activeTools.set(head.tool, {
          name: head.tool,
          lastFiredMs: now,
        });
        if (head.skill) {
          next.traversals.push({
            id: `${head.skill}->${head.tool}-${now}`,
            fromSkill: head.skill,
            toTool: head.tool,
            blocked: false,
            startMs: now,
          });
        }
      }

      // Validator block: mark the most recent traversal as blocked.
      if (head.type === "durable.validator.blocked") {
        const last = next.traversals[next.traversals.length - 1];
        if (last) last.blocked = true;
        next.status = "blocked";
      }

      // Workflow lifecycle.
      if (
        head.type === "durable.workflow.completed" ||
        head.type === "workflow.resolved"
      ) {
        next.status = "completed";
      }

      // Trim traversals older than animation duration.
      next.traversals = next.traversals.filter(
        (t) => now - t.startMs < TRAVERSAL_DURATION_MS * 2
      );

      return {
        ...next,
        activeSkills: new Map(next.activeSkills),
        activeTools: new Map(next.activeTools),
      };
    });
    // We deliberately depend on `events` only — phaseAliases is read at
    // event-fold time but its identity changes are fine to ignore.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events]);

  // Drive a periodic re-render so node opacity decays smoothly between events.
  useEffect(() => {
    const t = window.setInterval(() => force((n) => n + 1), 200);
    return () => window.clearInterval(t);
  }, []);

  // Render layout. The canvas is 900x540 with the centre at (450, 270).
  const W = 900;
  const H = 540;
  const cx = W / 2;
  const cy = H / 2;
  const phaseRadius = 150;
  const skillRadius = 230;
  const toolRadius = 320;
  const now = Date.now();

  const calm = !activeDomain
    || (activeDomain.activeSkills.size === 0 && activeDomain.activeTools.size === 0);

  // Compute positions.
  const phases = activeDomain?.phasesSeen ?? [];
  const phasePositions = useMemo(() => {
    const positions = new Map<string, { x: number; y: number }>();
    if (phases.length === 0) return positions;
    phases.forEach((p, i) => {
      const angle = (i * 2 * Math.PI) / Math.max(phases.length, 6) - Math.PI / 2;
      positions.set(p, {
        x: cx + Math.cos(angle) * phaseRadius,
        y: cy + Math.sin(angle) * phaseRadius,
      });
    });
    return positions;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phases.join("|"), cx, cy]);

  const skillPositions = useMemo(() => {
    const positions = new Map<string, { x: number; y: number }>();
    const skills = Array.from(activeDomain?.activeSkills.values() ?? []);
    const phaseAngle = activeDomain?.currentPhase
      ? (() => {
          const idx = phases.indexOf(activeDomain.currentPhase);
          if (idx < 0) return -Math.PI / 2;
          return (idx * 2 * Math.PI) / Math.max(phases.length, 6) - Math.PI / 2;
        })()
      : -Math.PI / 2;
    skills.forEach((s, i) => {
      const spread = (Math.PI * 140) / 180;
      const t = skills.length === 1 ? 0 : (i / (skills.length - 1)) - 0.5;
      const angle = phaseAngle + t * spread;
      positions.set(s.name, {
        x: cx + Math.cos(angle) * skillRadius,
        y: cy + Math.sin(angle) * skillRadius,
      });
    });
    return positions;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeDomain, phases.join("|"), cx, cy, skillRadius]);

  const toolPositions = useMemo(() => {
    const positions = new Map<string, { x: number; y: number }>();
    const tools = Array.from(activeDomain?.activeTools.values() ?? []);
    const total = Math.max(tools.length, 1);
    tools.forEach((t, i) => {
      const angle = (i * 2 * Math.PI) / total - Math.PI / 2;
      positions.set(t.name, {
        x: cx + Math.cos(angle) * toolRadius * 0.92,
        y: cy + Math.sin(angle) * toolRadius * 0.45,
      });
    });
    return positions;
  }, [activeDomain, cx, cy, toolRadius]);

  function nodeOpacity(lastFiredMs: number, fadeMs: number): number {
    const age = now - lastFiredMs;
    if (age < 200) return 1;
    if (age > fadeMs) return 0.18;
    return 1 - 0.82 * ((age - 200) / (fadeMs - 200));
  }

  const domainColour =
    activeDomain?.status === "blocked" ? "var(--error)" : "var(--accent)";

  return (
    <svg
      className="mindmap"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="Live mind-map of the active workflow"
    >
      {/* Faint guide rings, present even when calm. */}
      <circle cx={cx} cy={cy} r={phaseRadius} className="mindmap__ring" />
      <circle cx={cx} cy={cy} r={skillRadius} className="mindmap__ring" />
      <circle cx={cx} cy={cy} r={toolRadius * 0.55 + 10} className="mindmap__ring mindmap__ring--outer" />

      {/* Phase nodes on the inner ring. */}
      {phases.map((p) => {
        const pos = phasePositions.get(p)!;
        const isCurrent = p === activeDomain?.currentPhase;
        return (
          <g key={`phase-${p}`}>
            <circle
              cx={pos.x}
              cy={pos.y}
              r={isCurrent ? 7 : 4}
              className={`mindmap__phase ${isCurrent ? "mindmap__phase--current" : ""}`}
            />
            <text
              x={pos.x}
              y={pos.y - 14}
              className="mindmap__label mindmap__label--phase"
              textAnchor="middle"
            >
              {p}
            </text>
          </g>
        );
      })}

      {/* Lines from skills to tools (only the recent traversals between them). */}
      {Array.from(activeDomain?.activeSkills.values() ?? []).map((s) => {
        const sp = skillPositions.get(s.name);
        if (!sp) return null;
        return Array.from(activeDomain?.activeTools.values() ?? []).map((t) => {
          const tp = toolPositions.get(t.name);
          if (!tp) return null;
          const trav = activeDomain?.traversals.find(
            (tr) => tr.fromSkill === s.name && tr.toTool === t.name && now - tr.startMs < TRAVERSAL_DURATION_MS
          );
          if (!trav) return null;
          const progress = Math.min(1, (now - trav.startMs) / TRAVERSAL_DURATION_MS);
          const dotX = sp.x + (tp.x - sp.x) * progress;
          const dotY = sp.y + (tp.y - sp.y) * progress;
          return (
            <g key={`${s.name}-${t.name}-${trav.startMs}`}>
              <line
                x1={sp.x}
                y1={sp.y}
                x2={tp.x}
                y2={tp.y}
                className={`mindmap__edge ${trav.blocked ? "mindmap__edge--blocked" : ""}`}
              />
              <circle
                cx={dotX}
                cy={dotY}
                r={3.5}
                className={`mindmap__pulse ${trav.blocked ? "mindmap__pulse--blocked" : ""}`}
              />
            </g>
          );
        });
      })}

      {/* Skill nodes. */}
      {Array.from(activeDomain?.activeSkills.values() ?? []).map((s) => {
        const pos = skillPositions.get(s.name);
        if (!pos) return null;
        const op = nodeOpacity(s.lastFiredMs, SKILL_FADE_MS);
        return (
          <g key={`skill-${s.name}`} opacity={op}>
            <rect
              x={pos.x - 56}
              y={pos.y - 11}
              width={112}
              height={22}
              rx={3}
              className="mindmap__skill-tile"
            />
            <text x={pos.x} y={pos.y + 4} className="mindmap__label mindmap__label--skill" textAnchor="middle">
              {s.name}
            </text>
          </g>
        );
      })}

      {/* Tool nodes on the rim. */}
      {Array.from(activeDomain?.activeTools.values() ?? []).map((t) => {
        const pos = toolPositions.get(t.name);
        if (!pos) return null;
        const op = nodeOpacity(t.lastFiredMs, TOOL_FADE_MS);
        return (
          <g key={`tool-${t.name}`} opacity={op}>
            <circle cx={pos.x} cy={pos.y} r={5} className="mindmap__tool-dot" />
            <text x={pos.x} y={pos.y + 18} className="mindmap__label mindmap__label--tool" textAnchor="middle">
              {t.name}
            </text>
          </g>
        );
      })}

      {/* Centre badge — domain + workflow id. */}
      <g className={`mindmap__centre mindmap__centre--${activeDomain?.status ?? "idle"}`}>
        <circle cx={cx} cy={cy} r={50} className="mindmap__centre-ring" stroke={domainColour} />
        <text x={cx} y={cy - 4} textAnchor="middle" className="mindmap__centre-title">
          {activeDomain?.name ?? "—"}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" className="mindmap__centre-meta">
          {activeDomain?.workflowId ?? (status === "watching" ? "watching" : status)}
        </text>
      </g>

      {/* Calm overlay */}
      {calm && status === "watching" && (
        <text x={cx} y={H - 18} textAnchor="middle" className="mindmap__hint">
          watching for signal — fire a workflow to wake the page
        </text>
      )}
      {status === "offline" && (
        <text x={cx} y={H - 18} textAnchor="middle" className="mindmap__hint mindmap__hint--offline">
          observatory offline · start the FastAPI control plane
        </text>
      )}
    </svg>
  );
}
