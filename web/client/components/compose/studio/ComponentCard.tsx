import { paletteFor } from "./tokens";
import type { Component } from "./types";

// Small "root" card that hangs under a step. Click to zoom into full detail.
export function ComponentCard({ comp, onZoom }: { comp: Component; onZoom: () => void }) {
  const p = paletteFor(comp.type);
  const Icon = p.icon;
  return (
    <button
      onClick={onZoom}
      className={
        "group w-full cursor-zoom-in rounded-lg border border-l-[3px] border-slate-200 bg-white p-2 text-left shadow-sm " +
        "hover:shadow-md dark:border-slate-700 dark:bg-slate-900 " +
        p.borderL + " " + (comp.type === "authority" ? p.bg : "")
      }
    >
      <div className={"flex items-center gap-1.5 text-[8.5px] font-bold uppercase tracking-wide " + p.text}>
        <Icon size={11} />
        {p.label}
      </div>

      {comp.type === "persona" ? (
        <>
          <div className="mt-1 flex items-center gap-1.5">
            <span className="grid h-[19px] w-[19px] place-items-center rounded-full bg-gradient-to-br from-amber-400 to-rose-500 text-[8px] font-extrabold text-white">
              {initials(comp.name)}
            </span>
            <span className="text-[11px] font-semibold text-slate-900 dark:text-slate-100">{comp.name}</span>
          </div>
          <p className="mt-0.5 line-clamp-2 text-[9px] leading-tight text-slate-500 dark:text-slate-400">
            {comp.decisionPolicy}
          </p>
        </>
      ) : comp.type === "authority" ? (
        <table className="mt-1 w-full border-collapse text-[9px]">
          <tbody>
            {comp.tiers.map((t, i) => (
              <tr key={i} className="border-t border-slate-200/70 dark:border-slate-700/70">
                <td className="py-0.5 pr-1 font-semibold text-slate-900 dark:text-slate-100">{t.band}</td>
                <td className="py-0.5 text-slate-500 dark:text-slate-400">{t.approver.split(" ")[0]}</td>
                <td className={"py-0.5 text-right font-semibold " + (t.cosign ? p.text : "text-slate-400 dark:text-slate-500")}>
                  {t.cosign ? "+ " + t.cosign : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <>
          <div className="mt-0.5 text-[11px] font-semibold text-slate-900 dark:text-slate-100">{name(comp)}</div>
          <div className="text-[9px] text-slate-400 dark:text-slate-500">{sub(comp)}</div>
        </>
      )}
    </button>
  );
}

function name(c: Component): string {
  if (c.type === "entity" || c.type === "skill" || c.type === "tool") return c.name;
  return "";
}
function sub(c: Component): string {
  if (c.type === "entity") return c.canonical + (c.attributes[0] ? " · " + c.attributes[0].k : "");
  if (c.type === "tool") return c.system.replace(/[-_]/g, " ");
  if (c.type === "skill") return "generated";
  return "";
}
function initials(n: string): string {
  return n.split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}
