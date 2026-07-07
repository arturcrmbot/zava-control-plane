export function ThoughtStream({ text }: { text: string }) {
  return (
    <div className="h-full overflow-auto rounded-lg border border-slate-800 bg-slate-950/60 p-3">
      <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Thinking</p>
      <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-slate-400">{text || "…"}</pre>
    </div>
  );
}
