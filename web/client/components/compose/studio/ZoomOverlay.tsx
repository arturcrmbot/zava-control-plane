import { useEffect } from "react";
import { X, ArrowRight } from "lucide-react";
import { paletteFor, stepPalette } from "./tokens";
import type { Component, Composition, Step, ZoomTarget } from "./types";

export function ZoomOverlay({
  target,
  composition,
  onClose,
  onNavigate,
}: {
  target: ZoomTarget | null;
  composition: Composition | null;
  onClose: () => void;
  onNavigate: (t: ZoomTarget) => void;
}) {
  useEffect(() => {
    if (!target) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [target, onClose]);

  if (!target || !composition) return null;
  const step = composition.steps.find((s) => s.id === target.stepId);
  if (!step) return null;

  return (
    <div
      className="absolute inset-0 z-30 flex items-center justify-center bg-slate-900/40 p-8 backdrop-blur-sm dark:bg-slate-950/60"
      onClick={onClose}
    >
      <div
        className="max-h-[86%] w-full max-w-2xl overflow-auto rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
        onClick={(e) => e.stopPropagation()}
      >
        {target.kind === "step" ? (
          <StepDetail step={step} composition={composition} onClose={onClose} onNavigate={onNavigate} />
        ) : (
          <ComponentDetail comp={step.components[target.index]} step={step} composition={composition} onClose={onClose} onNavigate={onNavigate} />
        )}
      </div>
    </div>
  );
}

// ---------- shells ----------
function Header({ palette, tag, title, onClose }: { palette: ReturnType<typeof paletteFor>; tag: string; title: string; onClose: () => void }) {
  const Icon = palette.icon;
  return (
    <div className="flex items-center gap-3 border-b border-slate-100 px-6 py-4 dark:border-slate-800">
      <span className={"grid h-11 w-11 place-items-center rounded-xl " + palette.bg + " " + palette.text}>
        <Icon size={22} />
      </span>
      <div>
        <div className={"text-[10.5px] font-bold uppercase tracking-widest " + palette.text}>{tag}</div>
        <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100">{title}</h2>
      </div>
      <button onClick={onClose} className="ml-auto grid h-8 w-8 place-items-center rounded-lg border border-slate-200 text-slate-400 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800">
        <X size={16} />
      </button>
    </div>
  );
}

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[110px_1fr] items-start gap-3">
      <div className="pt-0.5 text-[11px] font-bold uppercase tracking-wide text-slate-400 dark:text-slate-500">{k}</div>
      <div className="text-[13.5px] text-slate-800 dark:text-slate-100">{children}</div>
    </div>
  );
}

function Source({ text }: { text: string }) {
  return <div className="rounded-r-lg border-l-[3px] border-blue-500 bg-blue-50 px-3 py-2 text-[12.5px] italic text-slate-600 dark:bg-blue-950/20 dark:text-slate-300">“{text}”</div>;
}

function Pill({ children, dot }: { children: React.ReactNode; dot?: string }) {
  return (
    <span className="mr-1.5 mb-1.5 inline-flex items-center gap-1.5 rounded-full border border-slate-200 px-2.5 py-1 text-[11.5px] text-slate-600 dark:border-slate-700 dark:text-slate-300">
      {dot && <span className={"h-1.5 w-1.5 rounded-full " + dot} />}
      {children}
    </span>
  );
}

// ---------- step ----------
function StepDetail({ step, composition, onClose, onNavigate }: { step: Step; composition: Composition; onClose: () => void; onNavigate: (t: ZoomTarget) => void }) {
  const idx = composition.steps.findIndex((s) => s.id === step.id);
  const p = stepPalette(step.kind);
  return (
    <>
      <Header palette={p} tag={`Step ${idx + 1} · ${laneText(step)}`} title={step.name} onClose={onClose} />
      <div className="grid gap-3.5 px-6 py-4">
        <Row k="What happens">{step.intent}</Row>
        <Row k="Owned by"><Pill dot="bg-amber-500">{cap(composition.function)}</Pill></Row>
        {step.components.length > 0 && (
          <Row k="Built here">
            <div className="grid grid-cols-2 gap-2.5">
              {step.components.map((c, i) => {
                const cp = paletteFor(c.type);
                const Icon = cp.icon;
                return (
                  <button key={i} onClick={() => onNavigate({ kind: "component", stepId: step.id, index: i })} className="cursor-zoom-in rounded-xl border border-slate-200 bg-slate-50/60 p-2.5 text-left hover:shadow-md dark:border-slate-700 dark:bg-slate-800/40">
                    <div className={"flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-wide " + cp.text}><Icon size={12} /> {cp.label}</div>
                    <div className="mt-0.5 text-[13px] font-semibold text-slate-900 dark:text-slate-100">{compTitle(c)}</div>
                    <div className="text-[11px] text-slate-400 dark:text-slate-500">zoom in →</div>
                  </button>
                );
              })}
            </div>
          </Row>
        )}
      </div>
    </>
  );
}

// ---------- components ----------
function ComponentDetail({ comp, step, composition, onClose, onNavigate }: { comp: Component; step: Step; composition: Composition; onClose: () => void; onNavigate: (t: ZoomTarget) => void }) {
  const p = paletteFor(comp.type);
  if (comp.type === "persona") {
    const authIdx = step.components.findIndex((c) => c.type === "authority");
    return (
      <>
        <Header palette={p} tag="Persona · human-in-the-loop" title={comp.name} onClose={onClose} />
        <div className="grid gap-3.5 px-6 py-4">
          <Row k="Role">Approver on the <b>{step.name}</b> step.</Row>
          <Row k="Decision policy">{comp.decisionPolicy}</Row>
          {authIdx >= 0 && (
            <Row k="Authority">
              <button className="text-blue-600 hover:underline dark:text-blue-400" onClick={() => onNavigate({ kind: "component", stepId: step.id, index: authIdx })}>Open authority matrix →</button>
            </Row>
          )}
        </div>
      </>
    );
  }
  if (comp.type === "authority") {
    return (
      <>
        <Header palette={p} tag="Governance · AGT authority matrix" title="Who can approve, and when" onClose={onClose} />
        <div className="grid gap-3.5 px-6 py-4">
          <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
            <table className="w-full border-collapse text-[12.5px]">
              <thead>
                <tr className="bg-rose-50 text-left text-[10px] uppercase tracking-wide text-rose-600 dark:bg-rose-950/30 dark:text-rose-400">
                  <th className="px-3 py-2">Amount band</th><th className="px-3 py-2">Approver</th><th className="px-3 py-2">Co-sign</th><th className="px-3 py-2">Escalates if</th>
                </tr>
              </thead>
              <tbody>
                {comp.tiers.map((t, i) => (
                  <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="px-3 py-2 font-semibold text-slate-900 dark:text-slate-100">{t.band}</td>
                    <td className="px-3 py-2 text-slate-600 dark:text-slate-300">{t.approver}</td>
                    <td className={"px-3 py-2 font-semibold " + (t.cosign ? "text-rose-600 dark:text-rose-400" : "text-slate-400 dark:text-slate-500")}>{t.cosign ? "+ " + t.cosign : "—"}</td>
                    <td className="px-3 py-2 text-slate-500 dark:text-slate-400">{t.escalatesIf ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Row k="Escalation">
            <div className="flex flex-wrap items-center gap-2">
              {comp.chain.map((n, i) => (
                <span key={i} className="flex items-center gap-2">
                  <span className={"rounded-lg border px-2.5 py-1.5 text-[12.5px] font-semibold " + (i === comp.chain.length - 1 ? "border-rose-300 bg-rose-50 text-rose-600 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-400" : "border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/50")}>{n}</span>
                  {i < comp.chain.length - 1 && <ArrowRight size={14} className="text-slate-400" />}
                </span>
              ))}
            </div>
          </Row>
          <Row k="From your doc"><Source text={comp.source} /></Row>
        </div>
      </>
    );
  }
  if (comp.type === "skill") {
    return (
      <>
        <Header palette={p} tag="Skill · generated" title={comp.name} onClose={onClose} />
        <div className="grid gap-3.5 px-6 py-4">
          <Row k="What it does">{step.intent}</Row>
          <Row k="Runs on">The <b>{step.name}</b> step, automatically.</Row>
          <Row k="Kind"><Pill dot="bg-violet-500">agent skill</Pill></Row>
        </div>
      </>
    );
  }
  if (comp.type === "tool") {
    return (
      <>
        <Header palette={p} tag="Tool · MCP integration" title={comp.name} onClose={onClose} />
        <div className="grid gap-3.5 px-6 py-4">
          <Row k="Call"><code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[13px] dark:bg-slate-800">{comp.name}</code></Row>
          <Row k="System">{comp.system.replace(/[-_]/g, " ")}</Row>
          <Row k="Operations">{comp.operations.map((o) => <Pill key={o}>{o}</Pill>)}</Row>
          <Row k="Used on">The <b>{step.name}</b> step.</Row>
        </div>
      </>
    );
  }
  // entity
  return (
    <>
      <Header palette={p} tag="Entity · projection" title={comp.name} onClose={onClose} />
      <div className="grid gap-3.5 px-6 py-4">
        <Row k="Maps to">Apex canonical <b>{comp.canonical}</b>.</Row>
        {comp.attributes.length > 0 && (
          <Row k="Fields">
            <div className="grid grid-cols-2 gap-2">
              {comp.attributes.map((a) => (
                <div key={a.k} className="rounded-lg border border-slate-200 bg-slate-50/60 px-2.5 py-2 dark:border-slate-700 dark:bg-slate-800/40">
                  <div className="text-[12.5px] font-semibold text-slate-900 dark:text-slate-100">{a.k}</div>
                  <div className="text-[10.5px] text-slate-400 dark:text-slate-500">{a.v}</div>
                </div>
              ))}
            </div>
          </Row>
        )}
        {comp.relations.length > 0 && (
          <Row k="Relations">{comp.relations.map((r, i) => <Pill key={i} dot="bg-emerald-500">{r.kind} → {r.target.replace("payload.", "")}</Pill>)}</Row>
        )}
        <Row k="Flows through">{composition.steps.map((s) => <Pill key={s.id}>{s.name}</Pill>)}</Row>
      </div>
    </>
  );
}

function laneText(step: Step): string {
  if (step.kind === "hitl") return "human sign-off";
  if (step.kind === "agent") return "analysis";
  return "automatic";
}
function cap(s: string): string { return s ? s[0].toUpperCase() + s.slice(1) : s; }
function compTitle(c: Component): string {
  if (c.type === "persona") return c.name;
  if (c.type === "authority") return `${c.tiers.length}-tier matrix`;
  if (c.type === "entity" || c.type === "skill" || c.type === "tool") return c.name;
  return "";
}
