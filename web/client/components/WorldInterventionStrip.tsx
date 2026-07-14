import type { InterventionStep } from "@client/lib/worldIntervention";

export function WorldInterventionStrip({
  testId,
  trace,
  steps,
  onTrace,
}: {
  testId: string;
  trace: string;
  steps: InterventionStep[];
  onTrace: (trace: string) => void;
}) {
  return (
    <section
      data-testid={testId}
      className="rounded-lg border border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/30 p-3"
    >
      <div className="flex items-center justify-between pb-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
          Durable intervention
        </h2>
        <button
          type="button"
          onClick={() => onTrace(trace)}
          className="text-[11px] font-mono text-emerald-700 dark:text-emerald-400 hover:underline"
        >
          {trace}
        </button>
      </div>
      <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-slate-700 dark:text-slate-200">
        {steps.map((step, index) => (
          <li key={step.eventId} className="flex items-center gap-1.5">
            {index > 0 && <span className="text-emerald-500">→</span>}
            <span className="font-medium">{step.label}</span>
            {step.detail && (
              <span className="font-mono text-[10px] text-slate-500 dark:text-slate-400">
                {step.detail}
              </span>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
