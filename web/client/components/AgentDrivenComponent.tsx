// web/client/components/AgentDrivenComponent.tsx — POC2 §4.21 AG-UI primitive.
//
// The Triage agent (cv-crystalliser) emits a structured component spec
// describing how it wants this candidate's scorecard rendered. Different
// roles get different layouts (e.g. a Creative Director scorecard surfaces a
// portfolio gallery; a Data Engineer scorecard surfaces a code-sample link).
//
// Spec shape — kept minimal for the spine. Track E2 expands the renderer
// vocabulary (timeline blocks, comparison tables, policy-citation chips, ...).

export type AgentComponentSpec =
  | { kind: "fact_grid"; title: string; facts: { label: string; value: string }[] }
  | { kind: "skill_chips"; title: string; skills: string[] }
  | { kind: "portfolio_gallery"; title: string; image_urls: string[] }
  | { kind: "policy_citation"; clause: string; excerpt: string }
  | { kind: "callout"; tone: "info" | "warn" | "success"; text: string };

export default function AgentDrivenComponent({ spec }: { spec: AgentComponentSpec }) {
  switch (spec.kind) {
    case "fact_grid":
      return (
        <div className="bg-white rounded border border-slate-200 p-3">
          <div className="text-xs uppercase tracking-wide text-slate-500">{spec.title}</div>
          <dl className="mt-2 grid grid-cols-2 gap-1 text-xs">
            {spec.facts.map(f => (
              <div key={f.label} className="contents">
                <dt className="text-slate-500">{f.label}</dt>
                <dd className="text-slate-800 font-medium">{f.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      );
    case "skill_chips":
      return (
        <div className="bg-white rounded border border-slate-200 p-3">
          <div className="text-xs uppercase tracking-wide text-slate-500">{spec.title}</div>
          <div className="mt-1 flex flex-wrap gap-1">
            {spec.skills.map(s => (
              <span key={s} className="text-[11px] bg-slate-100 text-slate-700 rounded px-2 py-0.5">{s}</span>
            ))}
          </div>
        </div>
      );
    case "portfolio_gallery":
      return (
        <div className="bg-white rounded border border-slate-200 p-3">
          <div className="text-xs uppercase tracking-wide text-slate-500">{spec.title}</div>
          <div className="mt-2 grid grid-cols-3 gap-2">
            {spec.image_urls.map(u => (
              <div key={u} className="aspect-square bg-slate-100 rounded text-[10px] text-slate-400 flex items-center justify-center">
                {u.split("/").pop()}
              </div>
            ))}
          </div>
        </div>
      );
    case "policy_citation":
      return (
        <div className="bg-amber-50 border border-amber-200 rounded p-3 text-xs">
          <div className="font-mono text-amber-900">{spec.clause}</div>
          <div className="mt-1 text-amber-800">{spec.excerpt}</div>
        </div>
      );
    case "callout": {
      const tone =
        spec.tone === "warn" ? "bg-amber-50 border-amber-200 text-amber-800"
        : spec.tone === "success" ? "bg-emerald-50 border-emerald-200 text-emerald-800"
        : "bg-blue-50 border-blue-200 text-blue-800";
      return <div className={`rounded border ${tone} p-3 text-xs`}>{spec.text}</div>;
    }
    default:
      return null;
  }
}
