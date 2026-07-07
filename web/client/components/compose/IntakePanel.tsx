import { useState } from "react";
import { UploadCloud } from "lucide-react";
import { createSession } from "./api";
import { ReplayPicker } from "./ReplayPicker";

export function IntakePanel({ onStarted }: { onStarted: (cid: string) => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  async function start(input: { text?: string; file?: File }) {
    setBusy(true);
    try { onStarted(await createSession(input)); }
    finally { setBusy(false); }
  }

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Compose a new domain</h1>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Drop a process document, or paste a description. An agent will read it, ask you anything ambiguous, draft a spec for your review, then build it live.</p>

      <label className="mt-6 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-blue-500 dark:hover:border-blue-500 p-8 text-slate-500 dark:text-slate-400"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) void start({ file: f }); }}>
        <UploadCloud size={28} />
        <span>Drop a PDF / docx / transcript here</span>
        <input type="file" className="hidden" accept=".pdf,.docx,.md,.txt"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void start({ file: f }); }} />
      </label>

      <div className="mt-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-3">
        <textarea className="h-40 w-full bg-transparent text-sm text-slate-900 dark:text-slate-100 resize-none focus:outline-none"
          placeholder="…or paste a process description" value={text} onChange={(e) => setText(e.target.value)} />
      </div>
      <button className="mt-3 rounded-md bg-blue-600 hover:bg-blue-500 px-4 py-2 font-medium text-white disabled:opacity-50"
        disabled={busy || !text.trim()} onClick={() => void start({ text })}>Compose</button>
      <ReplayPicker onStarted={onStarted} />
    </div>
  );
}
