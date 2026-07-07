import { useState } from "react";
import { HelpCircle, ChevronRight } from "lucide-react";

export function QuestionCard({
  question, onAnswer,
}: {
  question: { request_id: string; text: string; options: string[] };
  onAnswer: (request_id: string, answer: string) => void;
}) {
  const [text, setText] = useState("");
  const send = () => { if (text.trim()) onAnswer(question.request_id, text.trim()); };

  return (
    <div
      className="w-full rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-900"
      role="dialog"
      aria-label="Agent question"
    >
      <div className="flex items-center gap-2 text-[11.5px] font-bold uppercase tracking-wide text-blue-600 dark:text-blue-400">
        <HelpCircle size={15} /> One quick decision
      </div>
      <p className="mt-2 text-[16px] leading-relaxed text-slate-900 dark:text-slate-100">{question.text}</p>

      <div className="mt-4 flex flex-col gap-2">
        {question.options.map((o) => (
          <button
            key={o}
            onClick={() => onAnswer(question.request_id, o)}
            className="group flex w-full items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-[14px] leading-snug text-slate-800 transition-colors hover:border-blue-500 hover:bg-blue-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:border-blue-400 dark:hover:bg-blue-950/30"
          >
            <span>{o}</span>
            <ChevronRight size={16} className="shrink-0 text-slate-300 transition-colors group-hover:text-blue-500 dark:text-slate-600 dark:group-hover:text-blue-400" />
          </button>
        ))}
      </div>

      <div className="mt-4 flex items-stretch gap-2">
        <input
          className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-[14px] text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:placeholder:text-slate-500"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") send(); }}
          placeholder="or type your own answer…"
          aria-label="Free-text answer"
        />
        <button
          className="shrink-0 rounded-lg bg-blue-600 px-5 text-[14px] font-medium text-white hover:bg-blue-500 disabled:opacity-40 dark:text-slate-950"
          disabled={!text.trim()}
          onClick={send}
        >
          Send
        </button>
      </div>
    </div>
  );
}
