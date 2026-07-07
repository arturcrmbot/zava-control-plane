import { ToolCallCard } from "./ToolCallCard";
import type { ToolItem } from "./reducer";

export function ActivityTimeline({ narration, tools }: { narration: string; tools: ToolItem[] }) {
  return (
    <div className="flex h-full flex-col gap-3 overflow-auto">
      {narration && <p className="text-base font-medium text-slate-100">{narration}</p>}
      {tools.map((t) => <ToolCallCard key={t.id} tool={t} />)}
    </div>
  );
}
