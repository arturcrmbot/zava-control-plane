export function ThoughtStream({ text }: { text: string }) {
  return (
    <div className="h-full overflow-auto rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-3">
      <p className="mb-2 text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Thinking</p>
      <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-slate-600 dark:text-slate-400">{text || "…"}</pre>
    </div>
  );
}
