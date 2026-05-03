import { useEffect, useRef, useState } from "react";
import { useComposition } from "../lib/useComposition";
import { useInView } from "../lib/useInView";
import type { CompositionTree } from "../lib/types";

/**
 * Section 6 — compounding visualisation.
 *
 * Renders, in order:
 *   1. Cumulative size curve along the top — bars grow when the section
 *      enters the viewport, one after the other (the curve "draws itself").
 *   2. Per-domain headlines with new/reused counts.
 *   3. Tile detail per domain.
 *
 * The animation is one-shot — it only plays the first time the user
 * scrolls into the section.
 */

interface DomainProjection {
  name: string;
  status: "live" | "aspirational";
  newSkills: string[];
  reusedSkills: string[];
}

function project(tree: CompositionTree): DomainProjection[] {
  // Walk domains in the order the manifest declares them. Cumulative
  // "case of type" size grows as we encounter new skills.
  const seen = new Set<string>();
  const out: DomainProjection[] = [];
  for (const d of tree.domains) {
    const newOnes: string[] = [];
    const reused: string[] = [];
    for (const skillName of d.skills) {
      if (seen.has(skillName)) reused.push(skillName);
      else newOnes.push(skillName);
      seen.add(skillName);
    }
    out.push({
      name: d.name,
      status: d.status === "live" ? "live" : "aspirational",
      newSkills: newOnes,
      reusedSkills: reused,
    });
  }
  return out;
}

const STAGGER_MS = 280;

export function CompoundingDiagram() {
  const { data } = useComposition();
  const { ref, inView, enterCount } = useInView<HTMLDivElement>({ threshold: 0.25, debounceMs: 600 });

  // Reveal counter — increments per stagger interval once in view, capped
  // at the number of domains so we don't burn timers forever. Resets each
  // time the user re-enters the section.
  const [revealed, setRevealed] = useState(0);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (!inView || !data) return;
    // Reset on each re-entry so the animation replays.
    setRevealed(0);
    const total = data.domains.length;
    intervalRef.current = window.setInterval(() => {
      setRevealed((n) => {
        if (n >= total) {
          if (intervalRef.current) window.clearInterval(intervalRef.current);
          return n;
        }
        return n + 1;
      });
    }, STAGGER_MS);
    return () => {
      if (intervalRef.current) window.clearInterval(intervalRef.current);
    };
  }, [inView, enterCount, data]);

  if (!data) {
    return (
      <div ref={ref} className="map__placeholder map__placeholder--offline">
        Compounding visualisation needs the composition tree.
        <br />
        <span className="mono">
          Start the FastAPI control plane on :3001.
        </span>
      </div>
    );
  }

  const projections = project(data);
  let cumulative = 0;
  const projectionsWithCum = projections.map((p) => {
    cumulative += p.newSkills.length;
    return { ...p, cumulative };
  });
  const maxCum = Math.max(cumulative, 1);

  return (
    <div ref={ref} className={`compounding${inView ? " compounding--ready" : ""}`}>
      {/* Cumulative-size strip across the top. */}
      <div
        className="compounding__curve"
        style={{ gridTemplateColumns: `repeat(${data.domains.length}, 1fr)` }}
      >
        {projectionsWithCum.map((p, i) => {
          const isRevealed = i < revealed;
          const targetHeight = (p.cumulative / maxCum) * 100;
          return (
            <div className="compounding__curve-cell" key={p.name}>
              <div
                className={`compounding__curve-bar compounding__curve-bar--${p.status}`}
                style={{
                  height: isRevealed ? `${targetHeight}%` : "0%",
                }}
              >
                <div
                  className="compounding__curve-value"
                  style={{ opacity: isRevealed ? 1 : 0 }}
                >
                  {p.cumulative}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="compounding__curve-axis">
        <span>cumulative size of the case of type</span>
        <span className="compounding__curve-cap">{maxCum} skills cast in total</span>
      </div>

      {/* Per-domain headlines. */}
      <div
        className="compounding__headlines"
        style={{ gridTemplateColumns: `repeat(${data.domains.length}, 1fr)` }}
      >
        {projectionsWithCum.map((p, i) => {
          const isRevealed = i < revealed;
          const total = p.newSkills.length + p.reusedSkills.length;
          const pctReused = total === 0 ? null : Math.round((p.reusedSkills.length / total) * 100);
          return (
            <div
              className="compounding__head"
              key={p.name}
              style={{
                opacity: isRevealed ? 1 : 0,
                transform: isRevealed ? "translateY(0)" : "translateY(8px)",
              }}
            >
              <div className={`compounding__head-domain compounding__head-domain--${p.status}`}>
                {p.name}
              </div>
              {p.status === "aspirational" && p.newSkills.length === 0 ? (
                <div className="compounding__head-aspirational">next domain</div>
              ) : (
                <>
                  <div className="compounding__head-new">
                    {p.newSkills.length}
                    <span className="compounding__head-unit"> new</span>
                  </div>
                  {pctReused !== null && (
                    <div className="compounding__head-reused">
                      {p.reusedSkills.length} reused · {pctReused}%
                    </div>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Tile detail per domain. */}
      <div
        className="compounding__detail"
        style={{ gridTemplateColumns: `repeat(${data.domains.length}, 1fr)` }}
      >
        {projectionsWithCum.map((p, i) => {
          const isRevealed = i < revealed;
          return (
            <div
              className="compounding__detail-col"
              key={p.name}
              style={{
                opacity: isRevealed ? 1 : 0,
                transform: isRevealed ? "translateY(0)" : "translateY(12px)",
                transition: `opacity 600ms ease ${i * 80}ms, transform 600ms ease ${i * 80}ms`,
              }}
            >
              <div className="compounding__detail-tiles">
                {p.newSkills.map((s) => (
                  <span className="compounding__tile compounding__tile--new" key={`new-${s}`}>
                    {s}
                  </span>
                ))}
                {p.reusedSkills.length > 0 && (
                  <div className="compounding__detail-divider">{p.reusedSkills.length} reused</div>
                )}
                {p.reusedSkills.slice(0, 4).map((s) => (
                  <span className="compounding__tile compounding__tile--reused" key={`reused-${s}`}>
                    {s}
                  </span>
                ))}
                {p.reusedSkills.length > 4 && (
                  <span className="compounding__tile compounding__tile--reused">
                    + {p.reusedSkills.length - 4} more
                  </span>
                )}
                {p.status === "aspirational" && p.newSkills.length === 0 && (
                  <span className="compounding__tile compounding__tile--aspirational">to be cast</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="compounding__legend">
        <span>
          <span className="compounding__swatch compounding__swatch--new" /> new — cast
          for this domain
        </span>
        <span>
          <span className="compounding__swatch compounding__swatch--reused" /> reused
          — already in the case of type
        </span>
        <span>
          <span className="compounding__swatch compounding__swatch--aspirational" /> aspirational
          — next domains
        </span>
      </div>

      <p className="compounding__observation body">
        {(() => {
          const liveProjections = projections.filter((p) => p.status === "live");
          const first = liveProjections[0];
          const second = liveProjections[1];
          const last = liveProjections[liveProjections.length - 1];
          const totalSkillsCast = projections.reduce(
            (acc, p) => acc + p.newSkills.length,
            0,
          );
          if (!first) {
            return (
              <>
                The case of type holds <strong>{totalSkillsCast} skills</strong> so far.
              </>
            );
          }
          const lastTotal = last.newSkills.length + last.reusedSkills.length;
          const lastReusePct =
            lastTotal === 0 ? null : Math.round((last.reusedSkills.length / lastTotal) * 100);
          return (
            <>
              The first domain cast{" "}
              <strong>{first.newSkills.length} new skills</strong>.
              {second && (
                <>
                  {" "}The second reused{" "}
                  <strong>
                    {second.reusedSkills.length} of{" "}
                    {second.newSkills.length + second.reusedSkills.length}
                  </strong>
                  .
                </>
              )}
              {last !== first && last !== second && lastReusePct !== null && (
                <>
                  {" "}By the time we got to <strong>{last.name}</strong>,{" "}
                  {last.newSkills.length === 0 ? (
                    <>
                      every skill was already in the case of type —{" "}
                      <strong>{last.reusedSkills.length} of {lastTotal}</strong> reused.
                    </>
                  ) : (
                    <>
                      <strong>{lastReusePct}%</strong> of the work was reuse.
                    </>
                  )}
                </>
              )}
              {" "}And the skills are only the visible part. The harness, the
              MCPs, the identity, audit and governance — all of that was cast on
              day one and carries unchanged into every domain after.
            </>
          );
        })()}
      </p>
    </div>
  );
}
