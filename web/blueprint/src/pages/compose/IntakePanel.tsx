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
    <div className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold text-slate-100">Compose a new domain</h1>
      <p className="mt-1 text-slate-400">Drop a process document, or paste a description. An agent will read it, ask you anything ambiguous, draft a spec for your review, then build it live.</p>

      <label className="mt-6 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-700 p-10 text-slate-400 hover:border-sky-500"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) void start({ file: f }); }}>
        <UploadCloud size={28} />
        <span>Drop a PDF / docx / transcript here</span>
        <input type="file" className="hidden" accept=".pdf,.docx,.md,.txt"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void start({ file: f }); }} />
      </label>

      <textarea className="mt-4 h-40 w-full rounded-lg bg-slate-900 p-3 text-sm text-slate-100"
        placeholder="…or paste a process description" value={text} onChange={(e) => setText(e.target.value)} />
      <button className="mt-3 rounded-md bg-sky-600 px-4 py-2 font-medium text-white disabled:opacity-50"
        disabled={busy || !text.trim()} onClick={() => void start({ text })}>Compose</button>
      <ReplayPicker onStarted={onStarted} />
    </div>
  );
}
