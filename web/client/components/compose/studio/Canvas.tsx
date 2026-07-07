import { Loader2, ZoomIn } from "lucide-react";
import { StepCard } from "./StepCard";
import type { Composition, VisualStage, ZoomTarget } from "./types";

export function Canvas({
  composition,
  stage,
  onZoom,
}: {
  composition: Composition | null;
  stage: VisualStage;
  onZoom: (t: ZoomTarget) => void;
}) {
  const reading = stage === "read" || !composition;
  const built = stage === "build" || stage === "ready";

  return (
    <div className="relative flex-1 overflow-auto rounded-xl border border-dashed border-slate-200 bg-slate-50/40 p-3.5 dark:border-slate-700 dark:bg-slate-900/30">
      {!reading && (
        <div className="pointer-events-none absolute right-3 top-2 flex items-center gap-1.5 text-[10.5px] text-slate-400 dark:text-slate-500">
          <ZoomIn size={13} /> click any card to zoom
        </div>
      )}

      {reading ? (
        <div className="flex h-full min-h-[240px] flex-col items-center justify-center gap-3 text-slate-400 dark:text-slate-500">
          <Loader2 size={30} className="animate-spin text-violet-500 dark:text-violet-400" />
          <span className="text-sm">Reading your process…</span>
        </div>
      ) : (
        <div
          className="grid gap-2.5"
          style={{ gridTemplateColumns: `repeat(${composition!.steps.length}, minmax(0, 1fr))` }}
        >
          {composition!.steps.map((step) => (
            <StepCard
              key={step.id}
              step={step}
              built={built}
              onZoomStep={() => onZoom({ kind: "step", stepId: step.id })}
              onZoomComponent={(index) => onZoom({ kind: "component", stepId: step.id, index })}
            />
          ))}
        </div>
      )}
    </div>
  );
}
