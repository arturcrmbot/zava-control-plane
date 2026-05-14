import { useMemo, useState } from "react";
import type { CompositionTree, Skill, Mcp, Domain } from "../lib/types";

function plural(n: number, one: string, many: string = `${one}s`): string {
  return n === 1 ? `${n} ${one}` : `${n} ${many}`;
}

type HoverTarget =
  | { kind: "skill"; name: string }
  | { kind: "mcp"; name: string }
  | { kind: "domain"; name: string }
  | null;

interface Props {
  data: CompositionTree;
  /** Optional set of skill names that should pulse right now (live observatory). */
  pulsingSkills?: Set<string>;
  /** Optional set of (skill, tool) edges that should flare right now. */
  pulsingEdges?: Set<string>;
  /** Optional set of domain names that should glow right now. */
  pulsingDomains?: Set<string>;
}

/** Edge id helper. Used by both this component and the observatory subscriber. */
export function edgeId(skill: string, tool: string): string {
  return `${skill}->${tool}`;
}

export function CompositionMap({
  data,
  pulsingSkills,
  pulsingEdges,
  pulsingDomains,
}: Props) {
  const [hover, setHover] = useState<HoverTarget>(null);

  // Build lookups once per tree.
  const lookup = useMemo(() => {
    const skillsByName = new Map<string, Skill>();
    data.skills.forEach((s) => skillsByName.set(s.name, s));
    const mcpsByName = new Map<string, Mcp>();
    data.mcps.forEach((m) => mcpsByName.set(m.name, m));
    const domainsByName = new Map<string, Domain>();
    data.domains.forEach((d) => domainsByName.set(d.name, d));
    return { skillsByName, mcpsByName, domainsByName };
  }, [data]);

  // Compute the highlight set for the current hover target.
  const highlight = useMemo(() => {
    const skills = new Set<string>();
    const mcps = new Set<string>();
    const domains = new Set<string>();
    if (!hover) return { skills, mcps, domains, dim: false };

    if (hover.kind === "skill") {
      const s = lookup.skillsByName.get(hover.name);
      if (s) {
        skills.add(s.name);
        s.allowed_tools.forEach((t) => mcps.add(t));
        s.domains.forEach((d) => domains.add(d));
      }
    } else if (hover.kind === "mcp") {
      const m = lookup.mcpsByName.get(hover.name);
      if (m) {
        mcps.add(m.name);
        m.used_by_skills.forEach((sn) => {
          skills.add(sn);
          const s = lookup.skillsByName.get(sn);
          s?.domains.forEach((d) => domains.add(d));
        });
      }
    } else if (hover.kind === "domain") {
      const d = lookup.domainsByName.get(hover.name);
      if (d) {
        domains.add(d.name);
        d.skills.forEach((sn) => skills.add(sn));
        d.tools.forEach((tn) => mcps.add(tn));
      }
    }
    return { skills, mcps, domains, dim: true };
  }, [hover, lookup]);

  const isSkillActive = (name: string) =>
    highlight.dim ? highlight.skills.has(name) : true;
  const isMcpActive = (name: string) =>
    highlight.dim ? highlight.mcps.has(name) : true;
  const isDomainActive = (name: string) =>
    highlight.dim ? highlight.domains.has(name) : true;

  return (
    <div className="map" onMouseLeave={() => setHover(null)}>
      <header className="map__header">
        <div className="map__counts">
          <span>
            <strong>{data.counts.skills}</strong> skills
          </span>
          <span>
            <strong>{data.counts.mcps}</strong> MCP tools
          </span>
          <span>
            <strong>{data.counts.domains_live}</strong> domains operating
            <span className="map__counts-aside">
              · {data.counts.domains_aspirational} on the roadmap
            </span>
          </span>
        </div>
        <div className="map__legend">
          <span>Hover any tile to see what it composes.</span>
        </div>
      </header>

      <div className="map__row">
        <div className="map__row-label">Skills</div>
        <div className="map__row-cards">
          {data.skills.map((s) => {
            const active = isSkillActive(s.name);
            const pulsing = pulsingSkills?.has(s.name);
            const className = [
              "tile",
              "tile--skill",
              active ? "tile--active" : "tile--dim",
              pulsing ? "tile--pulse" : "",
            ]
              .filter(Boolean)
              .join(" ");
            return (
              <button
                key={s.name}
                className={className}
                onMouseEnter={() => setHover({ kind: "skill", name: s.name })}
                onFocus={() => setHover({ kind: "skill", name: s.name })}
                title={s.description}
              >
                {s.name}
              </button>
            );
          })}
        </div>
      </div>

      <div className="map__row">
        <div className="map__row-label">MCPs</div>
        <div className="map__row-cards">
          {[...data.mcps]
            .sort((a, b) => {
              // Wired MCPs first, then alphabetically; orphans bubble to the end.
              const aw = a.used_by_skills.length > 0 ? 0 : 1;
              const bw = b.used_by_skills.length > 0 ? 0 : 1;
              if (aw !== bw) return aw - bw;
              return a.name.localeCompare(b.name);
            })
            .map((m) => {
              const active = isMcpActive(m.name);
              const orphan = m.used_by_skills.length === 0;
              const className = [
                "tile",
                "tile--mcp",
                orphan ? "tile--idle" : "",
                active ? "tile--active" : "tile--dim",
              ]
                .filter(Boolean)
                .join(" ");
              const tooltip = orphan
                ? `${m.name} — capability available, no skill calls it yet`
                : `${m.name} — called by ${m.used_by_skills.length} skill${m.used_by_skills.length === 1 ? "" : "s"}`;
              return (
                <button
                  key={m.name}
                  className={className}
                  onMouseEnter={() => setHover({ kind: "mcp", name: m.name })}
                  onFocus={() => setHover({ kind: "mcp", name: m.name })}
                  title={tooltip}
                >
                  {m.name}
                </button>
              );
            })}
        </div>
      </div>

      {(() => {
        const liveDomains = data.domains.filter((d) => d.status === "live");
        const aspirationalDomains = data.domains.filter((d) => d.status !== "live");
        const renderTile = (d: Domain) => {
          const active = isDomainActive(d.name);
          const pulsing = pulsingDomains?.has(d.name);
          const className = [
            "tile",
            "tile--domain",
            `tile--${d.status}`,
            active ? "tile--active" : "tile--dim",
            pulsing ? "tile--pulse" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <button
              key={d.name}
              className={className}
              onMouseEnter={() => setHover({ kind: "domain", name: d.name })}
              onFocus={() => setHover({ kind: "domain", name: d.name })}
            >
              <span className="tile__title">{d.name}</span>
              <span className="tile__meta">
                {d.status === "live"
                  ? `${plural(d.skills.length, "skill")} · ${plural(d.tools.length, "tool")}`
                  : "on the roadmap"}
              </span>
            </button>
          );
        };
        return (
          <>
            <div className="map__row map__row--domains">
              <div className="map__row-label">Domains · live</div>
              <div className="map__row-cards map__row-cards--domains">
                {liveDomains.map(renderTile)}
              </div>
            </div>
            {aspirationalDomains.length > 0 && (
              <div className="map__row map__row--aspirational">
                <div className="map__row-label">Roadmap</div>
                <div className="map__row-cards map__row-cards--domains">
                  {aspirationalDomains.map(renderTile)}
                </div>
              </div>
            )}
          </>
        );
      })()}

      <footer className="map__footer">
        {hover ? (
          <span className="map__hover-detail">
            {hover.kind === "skill" && (
              <>
                <strong>{hover.name}</strong> →{" "}
                {Array.from(highlight.mcps).join(", ") || "no MCP tools"} ·
                used by {Array.from(highlight.domains).join(", ") || "no domains yet"}
              </>
            )}
            {hover.kind === "mcp" && (
              <>
                <strong>{hover.name}</strong>
                {Array.from(highlight.skills).length === 0 ? (
                  <> · capability available, no skill calls it yet</>
                ) : (
                  <> ← called by {Array.from(highlight.skills).join(", ")}</>
                )}
              </>
            )}
            {hover.kind === "domain" && (
              <>
                <strong>{hover.name}</strong> composes{" "}
                {plural(Array.from(highlight.skills).length, "skill")} ·{" "}
                {plural(Array.from(highlight.mcps).length, "tool")}
              </>
            )}
          </span>
        ) : (
          <span className="map__hover-empty">
            Each row reads from disk: <code>api/server/skills/</code>,{" "}
            <code>api/server/mcp_tools/</code>, and the domain manifest.
          </span>
        )}
      </footer>
    </div>
  );
}
