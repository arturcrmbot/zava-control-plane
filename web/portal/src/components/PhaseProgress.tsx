import { PHASES, resolvePhase } from "../lib/phases";

const STYLES = {
  done:    { bubble: "phase-bubble phase-bubble-done",    label: "phase-label-done",    rail: "phase-rail-done" },
  current: { bubble: "phase-bubble phase-bubble-current", label: "phase-label-current", rail: "phase-rail-current" },
  todo:    { bubble: "phase-bubble phase-bubble-todo",    label: "phase-label-todo",    rail: "phase-rail-todo" },
} as const;

export default function PhaseProgress({ phase }: { phase: string }) {
  const resolved = resolvePhase(phase);
  const activeIdx = Math.max(PHASES.findIndex((p) => p.id === resolved), 0);

  return (
    <ol className="grid grid-cols-7 gap-1 sm:gap-2 text-[11px] sm:text-xs">
      {PHASES.map((p, i) => {
        const state = i < activeIdx ? "done" : i === activeIdx ? "current" : "todo";
        const s = STYLES[state];
        return (
          <li key={p.id} className="flex flex-col items-center text-center relative">
            <div className="flex items-center w-full">
              {i > 0 && <div className={`flex-1 h-0.5 ${s.rail}`}/>}
              <span className={s.bubble}>{state === "done" ? "✓" : i + 1}</span>
              {i < PHASES.length - 1 && <div className={`flex-1 h-0.5 ${s.rail}`}/>}
            </div>
            <span className={`mt-2 ${s.label}`}>{p.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
