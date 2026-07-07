import { useState } from "react";

export function QuestionCard({
  question, onAnswer,
}: {
  question: { request_id: string; text: string; options: string[] };
  onAnswer: (request_id: string, answer: string) => void;
}) {
  const [text, setText] = useState("");
  return (
    <div className="rounded-xl border border-amber-500/50 bg-slate-900 p-5 shadow-xl" role="dialog" aria-label="Agent question">
      <p className="text-sm text-amber-300">The agent needs a decision</p>
      <p className="mt-1 text-base text-slate-100">{question.text}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {question.options.map((o) => (
          <button key={o} className="rounded-full border border-slate-600 px-3 py-1 text-sm hover:bg-slate-800"
            onClick={() => onAnswer(question.request_id, o)}>{o}</button>
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <input className="flex-1 rounded-md bg-slate-800 px-3 py-1.5 text-sm" value={text}
          onChange={(e) => setText(e.target.value)} placeholder="or type an answer…" aria-label="Free-text answer" />
        <button className="rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium disabled:opacity-50"
          disabled={!text.trim()} onClick={() => onAnswer(question.request_id, text.trim())}>Send</button>
      </div>
    </div>
  );
}
