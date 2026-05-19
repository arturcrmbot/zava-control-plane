import { useEffect, useRef, useState } from "react";
import { useComposition } from "../lib/useComposition";
import { useInView } from "../lib/useInView";
import type { CompositionTree } from "../lib/types";

/**
 * Section 6 — compounding visualisation.
 *
 * Premise: surface "skill reuse" massively undersells the story. The thing
 * that actually compounds is the *platform* — the harness, the MCPs, the
 * validators, the identity, the audit. Each new domain ships a tiny bit of
 * new code on top of an enormous reused base. This visualisation makes
 * that proportion legible.
 *
 * Per-domain stacked horizontal bar: each bar represents the total "build
 * surface" you'd otherwise have written from scratch. The vast majority is
 * always reused. The new sliver shrinks domain by domain.
 */

interface DomainBreakdown {
  name: string;
  status: "live" | "aspirational";
  newSkills: string[];
  reusedSkills: string[];
  /** MCP tools wired into this domain — all reused after the first cast. */
  reusedMcps: number;
  /** Always-on guarantees inherited by every domain (identity/validator/audit/policy). */
  reusedGuarantees: number;
  /** Harness primitives inherited by every domain (lifecycle, queue, retry, observability, cost). */
  reusedHarness: number;
}

/** Constant platform surface inherited by every domain regardless of size. */
const HARNESS_PRIMITIVES = 8; // workflow lifecycle, retry, queue, OTEL spans, cost attribution, dispatch, persistence, hooks
const GUARANTEE_PRIMITIVES = 4; // identity-on-action, validator-before-send, audit-ledger, policy-as-data

function buildBreakdowns(tree: CompositionTree): DomainBreakdown[] {
  const seen = new Set<string>();
  const out: DomainBreakdown[] = [];
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
      reusedMcps: d.tools.length,
      reusedGuarantees: GUARANTEE_PRIMITIVES,
      reusedHarness: HARNESS_PRIMITIVES,
    });
  }
  return out;
}

function totalSurface(b: DomainBreakdown): number {
  return (
    b.newSkills.length +
    b.reusedSkills.length +
    b.reusedMcps +
    b.reusedGuarantees +
    b.reusedHarness
  );
}

function pct(part: number, whole: number): number {
  if (whole === 0) return 0;
  return Math.round((part / whole) * 100);
}

const STAGGER_MS = 240;

export function CompoundingDiagram() {
  const { data } = useComposition();
  const { ref, inView, enterCount } = useInView<HTMLDivElement>({
    threshold: 0.25,
    debounceMs: 600,
  });

  const [revealed, setRevealed] = useState(0);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (!inView || !data) return;
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
        <span className="mono">Start the FastAPI control plane on :3101.</span>
      </div>
    );
  }

  const breakdowns = buildBreakdowns(data);

  // Use the largest domain surface as the bar scale so every bar reads on
  // the same axis. (All bars will be close to full because the harness
  // dominates; that's the point.)
  const maxSurface = Math.max(...breakdowns.map(totalSurface), 1);

  return (
    <div ref={ref} className={`compounding-v2${inView ? " compounding-v2--ready" : ""}`}>
      {/* Per-domain stacked bars. */}
      <div className="compounding-v2__bars" role="img" aria-label="Per-domain build surface broken down by what's reused vs newly cast">
        {breakdowns.map((b, i) => {
          const isRevealed = i < revealed;
          const total = totalSurface(b);
          const widthPct = (total / maxSurface) * 100;
          const segments = [
            {
              kind: "harness" as const,
              label: "harness",
              count: b.reusedHarness,
              cls: "compounding-v2__seg--harness",
            },
            {
              kind: "guarantees" as const,
              label: "guarantees",
              count: b.reusedGuarantees,
              cls: "compounding-v2__seg--guarantees",
            },
            {
              kind: "mcps" as const,
              label: "MCPs",
              count: b.reusedMcps,
              cls: "compounding-v2__seg--mcps",
            },
            {
              kind: "reused-skills" as const,
              label: "reused skills",
              count: b.reusedSkills.length,
              cls: "compounding-v2__seg--reused-skills",
            },
            {
              kind: "new-skills" as const,
              label: "new skills",
              count: b.newSkills.length,
              cls: "compounding-v2__seg--new-skills",
            },
          ];
          const newPct = pct(b.newSkills.length, total);
          const reusePct = 100 - newPct;
          return (
            <div
              key={b.name}
              className={`compounding-v2__row compounding-v2__row--${b.status}${
                isRevealed ? " compounding-v2__row--revealed" : ""
              }`}
            >
              <div className="compounding-v2__row-label">
                <span className="compounding-v2__row-name">{b.name}</span>
                <span className="compounding-v2__row-stat">
                  {b.status === "aspirational" && total === HARNESS_PRIMITIVES + GUARANTEE_PRIMITIVES ? (
                    <>{HARNESS_PRIMITIVES + GUARANTEE_PRIMITIVES} primitives ready · 0 new yet</>
                  ) : (
                    <>
                      <strong>{reusePct}%</strong> reuse
                      {b.newSkills.length > 0 && (
                        <>
                          {" "}· <strong>{b.newSkills.length}</strong> new skill
                          {b.newSkills.length === 1 ? "" : "s"}
                        </>
                      )}
                    </>
                  )}
                </span>
              </div>
              <div className="compounding-v2__bar" style={{ width: `${widthPct}%` }}>
                {segments.map((seg) => {
                  if (seg.count === 0) return null;
                  const segPct = (seg.count / total) * 100;
                  return (
                    <div
                      key={seg.kind}
                      className={`compounding-v2__seg ${seg.cls}`}
                      style={{ flex: `0 0 ${segPct}%` }}
                      title={`${seg.count} ${seg.label}`}
                    >
                      <span className="compounding-v2__seg-count">{seg.count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend keyed to the segment colours above. */}
      <div className="compounding-v2__legend">
        <span>
          <span className="compounding-v2__swatch compounding-v2__swatch--harness" /> Harness
          primitives
        </span>
        <span>
          <span className="compounding-v2__swatch compounding-v2__swatch--guarantees" /> Always‑on
          guarantees
        </span>
        <span>
          <span className="compounding-v2__swatch compounding-v2__swatch--mcps" /> MCPs wired in
        </span>
        <span>
          <span className="compounding-v2__swatch compounding-v2__swatch--reused-skills" /> Skills
          already in the case
        </span>
        <span>
          <span className="compounding-v2__swatch compounding-v2__swatch--new-skills" /> New skills
          cast for this domain
        </span>
      </div>

      {/* Headline numbers + narrative. */}
      <div className="compounding-v2__summary">
        {(() => {
          const live = breakdowns.filter((b) => b.status === "live");
          if (live.length === 0) return null;
          const totalsByDomain = live.map((b) => ({
            b,
            total: totalSurface(b),
            newCount: b.newSkills.length,
          }));
          const newCounts = totalsByDomain.map((x) => x.newCount);
          const minNew = Math.min(...newCounts);
          const maxNew = Math.max(...newCounts);
          const reusedTotals = totalsByDomain.map(
            (x) => x.total - x.newCount,
          );
          const avgReusePct = Math.round(
            (totalsByDomain.reduce((acc, x) => acc + (x.total - x.newCount) / x.total, 0) /
              totalsByDomain.length) *
              100,
          );
          return (
            <p className="compounding-v2__observation body">
              The first domain (<strong>{totalsByDomain[0].b.name}</strong>) rode on{" "}
              <strong>{totalsByDomain[0].total - totalsByDomain[0].newCount}</strong>{" "}
              already‑cast primitives — harness, guarantees, MCPs, infrastructure.
              By the time we got to{" "}
              <strong>{totalsByDomain[totalsByDomain.length - 1].b.name}</strong>,
              the new code added was{" "}
              <strong>{minNew} skill</strong>
              {minNew === 1 ? "" : "s"} against a base of{" "}
              <strong>{reusedTotals[reusedTotals.length - 1]}</strong> already‑there
              parts. <strong>That</strong> is reuse. Across the live domains, an
              average of <strong>{avgReusePct}%</strong> of every shipment came from
              the case of type — not because we keep rebuilding the same skill, but
              because the platform itself is the thing we cast on day one. New skills
              ranged from <strong>{minNew}</strong> to <strong>{maxNew}</strong> per
              domain; the harness, the validators, the audit ledger, the identity
              primitives — all carried.
            </p>
          );
        })()}
      </div>
    </div>
  );
}
