import { useMemories } from "@client/hooks/useMemoryQueries";

export default function MemoriesColumn({ domain }: { domain: string }) {
  const { memories, count, isLoading } = useMemories(domain);

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
          🧠 Memories
        </span>
        <span className="text-xs text-slate-500 dark:text-slate-400">
          ({count})
        </span>
      </div>
      {isLoading ? (
        <div className="text-xs text-slate-400">Loading…</div>
      ) : memories.length === 0 ? (
        <div className="text-xs text-slate-400 italic">No memories yet. Agent runs will populate this automatically.</div>
      ) : (
        <ul className="space-y-2">
          {memories.map((m, i) => (
            <li key={m.id || i} className="bg-white border border-slate-200 rounded-lg p-3 dark:bg-slate-900 dark:border-slate-700">
              <div className="text-sm text-slate-800 dark:text-slate-200">
                {m.memory}
              </div>
              {m.metadata?.agent_skill && (
                <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  {m.metadata.agent_skill}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
