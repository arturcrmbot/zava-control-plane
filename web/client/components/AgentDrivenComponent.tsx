// web/client/components/AgentDrivenComponent.tsx — POC2 §4.21 AG-UI primitive.
//
// The Triage agent (cv-crystalliser) emits a structured component spec
// describing how it wants this candidate's scorecard rendered. Different
// roles get different layouts (e.g. a Creative Director scorecard surfaces a
// portfolio gallery; a Data Engineer scorecard surfaces a code-sample link).
//
// Spec shape — kept minimal for the spine. Track E2 expands the renderer
// vocabulary (timeline blocks, comparison tables, policy-citation chips, ...).
//
// POC3 Phase 5 extends with three creative-campaign kinds:
//   - brief_scorecard: structured creative brief (audience, mandatory msgs, KPIs)
//   - concept_tiles:   3 strategic routes × 4 stills + brand_fit/distinctiveness
//   - storyboard_strip: 6 storyboard frames

export type AgentComponentSpec =
  | { kind: "fact_grid"; title: string; facts: { label: string; value: string }[] }
  | { kind: "skill_chips"; title: string; skills: string[] }
  | { kind: "portfolio_gallery"; title: string; image_urls: string[] }
  | { kind: "policy_citation"; clause: string; excerpt: string }
  | { kind: "callout"; tone: "info" | "warn" | "success"; text: string }
  | {
      kind: "brief_scorecard";
      title: string;
      client_brand: string;
      category: string;
      audience: string;
      mandatory_messages: string[];
      channels: string[];
      kpis: Record<string, string>;
      jurisdictions?: string[];
      constraints?: string[];
    }
  | {
      kind: "concept_tiles";
      title: string;
      routes: Array<{
        route_name: string;
        headline?: string;
        description?: string;
        stills: string[];
        brand_fit: number;
        distinctiveness: number;
      }>;
      onLockRoute?: (routeName: string) => void;
      lockedRoute?: string;
    }
  | {
      kind: "storyboard_strip";
      title: string;
      frames: string[];
      frame_captions?: string[];
    };

function _staticUrl(maybeRelative: string): string {
  // Stub agent returns paths like 'creative-campaign/cached/BRF-001/route-A/1.svg'.
  // The static route prefix is '/api/static/'. Already-absolute URLs (real
  // gpt-image-2 outputs in Phase 3) pass through unchanged.
  if (maybeRelative.startsWith("http") || maybeRelative.startsWith("/")) return maybeRelative;
  return `/api/static/${maybeRelative}`;
}

export default function AgentDrivenComponent({ spec }: { spec: AgentComponentSpec }) {
  switch (spec.kind) {
    case "fact_grid":
      return (
        <div className="bg-white dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-700 p-3">
          <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{spec.title}</div>
          <dl className="mt-2 grid grid-cols-2 gap-1 text-xs">
            {spec.facts.map(f => (
              <div key={f.label} className="contents">
                <dt className="text-slate-500 dark:text-slate-400">{f.label}</dt>
                <dd className="text-slate-800 dark:text-slate-100 font-medium">{f.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      );
    case "skill_chips":
      return (
        <div className="bg-white dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-700 p-3">
          <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{spec.title}</div>
          <div className="mt-1 flex flex-wrap gap-1">
            {spec.skills.map(s => (
              <span key={s} className="text-[11px] bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded px-2 py-0.5">{s}</span>
            ))}
          </div>
        </div>
      );
    case "portfolio_gallery":
      return (
        <div className="bg-white dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-700 p-3">
          <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{spec.title}</div>
          <div className="mt-2 grid grid-cols-3 gap-2">
            {spec.image_urls.map(u => (
              <div key={u} className="aspect-square bg-slate-100 dark:bg-slate-800 rounded text-[10px] text-slate-400 dark:text-slate-500 flex items-center justify-center">
                {u.split("/").pop()}
              </div>
            ))}
          </div>
        </div>
      );
    case "policy_citation":
      return (
        <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded p-3 text-xs">
          <div className="font-mono text-amber-900">{spec.clause}</div>
          <div className="mt-1 text-amber-800">{spec.excerpt}</div>
        </div>
      );
    case "callout": {
      const tone =
        spec.tone === "warn" ? "bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800 text-amber-800"
        : spec.tone === "success" ? "bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800 text-emerald-800"
        : "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800 text-blue-800";
      return <div className={`rounded border ${tone} p-3 text-xs`}>{spec.text}</div>;
    }
    case "brief_scorecard":
      return (
        <div className="panel" data-testid="creative-brief-scorecard">
          <div className="panel-header flex items-center justify-between">
            <span>{spec.title}</span>
            <span className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">{spec.client_brand} · {spec.category.replace(/_/g, " ")}</span>
          </div>
          <div className="panel-body space-y-3 text-xs">
            <div>
              <div className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Audience</div>
              <div className="text-slate-800 dark:text-slate-100 mt-0.5">{spec.audience}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Mandatory messages</div>
              <ul className="mt-0.5 list-disc list-inside text-slate-800 dark:text-slate-100 space-y-0.5">
                {spec.mandatory_messages.map(m => <li key={m}>{m}</li>)}
              </ul>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Channels</div>
                <div className="mt-0.5 flex flex-wrap gap-1">
                  {spec.channels.map(c => (
                    <span key={c} className="text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded px-1.5 py-0.5">{c}</span>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">KPIs</div>
                <div className="mt-0.5 space-y-0.5">
                  {Object.entries(spec.kpis).map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between gap-2">
                      <span className="text-slate-500 dark:text-slate-400 capitalize">{k.replace(/_/g, " ")}</span>
                      <span className="font-semibold text-slate-800 dark:text-slate-100">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            {spec.jurisdictions && spec.jurisdictions.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Jurisdictions</div>
                <div className="mt-0.5 flex gap-1">
                  {spec.jurisdictions.map(j => (
                    <span key={j} className="text-[10px] bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300 ring-1 ring-blue-200 rounded px-1.5 py-0.5 font-mono">{j}</span>
                  ))}
                </div>
              </div>
            )}
            {spec.constraints && spec.constraints.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">Constraints</div>
                <ul className="mt-0.5 list-disc list-inside text-slate-700 dark:text-slate-200 space-y-0.5">
                  {spec.constraints.map(c => <li key={c}>{c}</li>)}
                </ul>
              </div>
            )}
          </div>
        </div>
      );
    case "concept_tiles":
      return (
        <div className="panel" data-testid="creative-concept-tiles">
          <div className="panel-header flex items-center justify-between">
            <span>{spec.title}</span>
            <span className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">{spec.routes.length} routes</span>
          </div>
          <div className="panel-body grid grid-cols-1 md:grid-cols-3 gap-3">
            {spec.routes.map(r => {
              const locked = spec.lockedRoute === r.route_name;
              const score = (r.brand_fit + r.distinctiveness) / 2;
              return (
                <div
                  key={r.route_name}
                  data-testid={`creative-concept-route-${r.route_name}`}
                  className={`rounded border p-2 space-y-2 ${locked ? "border-emerald-400 bg-emerald-50 dark:bg-emerald-950/30/40" : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900"}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-semibold text-slate-800 dark:text-slate-100">
                      {r.headline ?? r.route_name}
                      <span className="ml-1.5 text-[10px] font-mono text-slate-500 dark:text-slate-400">{r.route_name}</span>
                    </div>
                    {locked && <span className="text-[10px] uppercase tracking-wide bg-emerald-100 text-emerald-700 dark:text-emerald-400 rounded px-1.5 py-0.5">locked</span>}
                  </div>
                  {r.description && <div className="text-[11px] text-slate-600 dark:text-slate-300">{r.description}</div>}
                  <div className="grid grid-cols-2 gap-1">
                    {r.stills.slice(0, 4).map(s => (
                      <img
                        key={s}
                        src={_staticUrl(s)}
                        alt={s}
                        className="aspect-video w-full object-cover rounded bg-slate-100 dark:bg-slate-800"
                      />
                    ))}
                  </div>
                  <div className="flex items-center justify-between gap-2 text-[10px]">
                    <div className="flex gap-2">
                      <span className="text-slate-500 dark:text-slate-400">brand-fit <span className="text-slate-800 dark:text-slate-100 font-semibold">{r.brand_fit.toFixed(2)}</span></span>
                      <span className="text-slate-500 dark:text-slate-400">distinct <span className="text-slate-800 dark:text-slate-100 font-semibold">{r.distinctiveness.toFixed(2)}</span></span>
                    </div>
                    <span className={`px-1.5 py-0.5 rounded font-semibold ${score >= 0.85 ? "bg-emerald-100 text-emerald-700 dark:text-emerald-400" : score >= 0.7 ? "bg-amber-100 text-amber-700 dark:text-amber-400" : "bg-red-100 text-red-700 dark:text-red-400"}`}>{(score * 100).toFixed(0)}</span>
                  </div>
                  {spec.onLockRoute && !locked && (
                    <button
                      onClick={() => spec.onLockRoute && spec.onLockRoute(r.route_name)}
                      data-testid={`creative-lock-${r.route_name}`}
                      className="w-full text-xs bg-blue-600 hover:bg-blue-700 text-white rounded px-2 py-1.5 font-medium transition-colors"
                    >
                      Lock route
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      );
    case "storyboard_strip":
      return (
        <div className="panel" data-testid="creative-storyboard-strip">
          <div className="panel-header flex items-center justify-between">
            <span>{spec.title}</span>
            <span className="text-[10px] uppercase tracking-wide text-slate-500 dark:text-slate-400">{spec.frames.length} frames</span>
          </div>
          <div className="panel-body grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
            {spec.frames.map((f, i) => (
              <div key={f} className="space-y-1">
                <img
                  src={_staticUrl(f)}
                  alt={`frame ${i + 1}`}
                  className="aspect-video w-full object-cover rounded bg-slate-100 dark:bg-slate-800"
                />
                <div className="text-[10px] text-slate-600 dark:text-slate-300 leading-tight">
                  <span className="font-mono text-slate-400 dark:text-slate-500">{(i + 1).toString().padStart(2, "0")}</span>{" "}
                  {spec.frame_captions?.[i] ?? ""}
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    default:
      return null;
  }
}
