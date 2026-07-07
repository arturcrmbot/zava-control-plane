import { useState } from "react";
import { UploadCloud, Wand2, Loader2, ArrowRight } from "lucide-react";
import { createSession } from "./api";
import { ReplayPicker } from "./ReplayPicker";

const FLOW = ["Read", "Design", "Build", "Ready"];

export function IntakePanel({ onStarted }: { onStarted: (cid: string, source?: string) => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  async function start(input: { text?: string; file?: File }) {
    setBusy(true);
    try { onStarted(await createSession(input), input.text); }
    finally { setBusy(false); }
  }

  return (
    <div className="flex h-full items-center justify-center overflow-auto p-6">
      <div className="w-full max-w-xl py-8">
        <div className="text-center">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-600/25 dark:text-slate-950">
            <Wand2 size={24} />
          </div>
          <h1 className="mt-4 text-[26px] font-bold tracking-tight text-slate-900 dark:text-slate-100">Compose a new process</h1>
          <p className="mx-auto mt-2 max-w-md text-[14px] leading-relaxed text-slate-500 dark:text-slate-400">
            Drop a document or paste a description. I'll read it, ask you anything unclear, show you the plan, then build it live.
          </p>
          <div className="mt-4 flex items-center justify-center gap-2 text-[11.5px] font-medium text-slate-400 dark:text-slate-500">
            {FLOW.map((s, i) => (
              <span key={s} className="flex items-center gap-2">
                <span className="rounded-full bg-slate-100 px-2.5 py-1 dark:bg-slate-800">{s}</span>
                {i < FLOW.length - 1 && <ArrowRight size={12} className="text-slate-300 dark:text-slate-600" />}
              </span>
            ))}
          </div>
        </div>

        <label
          className="group mt-7 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 bg-white p-9 text-slate-500 transition-colors hover:border-blue-500 hover:bg-blue-50/40 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400 dark:hover:border-blue-500 dark:hover:bg-blue-950/10"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) void start({ file: f }); }}
        >
          <UploadCloud size={30} className="text-slate-400 transition-colors group-hover:text-blue-500 dark:text-slate-500" />
          <span className="text-[14px] font-medium text-slate-700 dark:text-slate-200">Drop a document here</span>
          <span className="text-[12px] text-slate-400 dark:text-slate-500">PDF, Word, or a transcript</span>
          <input type="file" className="hidden" accept=".pdf,.docx,.md,.txt"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) void start({ file: f }); }} />
        </label>

        <div className="my-4 flex items-center gap-3 text-[11px] font-medium uppercase tracking-wide text-slate-300 dark:text-slate-600">
          <span className="h-px flex-1 bg-slate-200 dark:bg-slate-800" /> or <span className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
        </div>

        <textarea
          className="h-36 w-full resize-none rounded-2xl border border-slate-200 bg-white p-4 text-[14px] leading-relaxed text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500"
          placeholder="Paste a process description — e.g. “Staff request funding for capital assets. We check the budget, an analyst reviews risk, then a controller signs off…”"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />

        <button
          className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-[15px] font-semibold text-white shadow-lg shadow-blue-600/20 hover:bg-blue-500 disabled:opacity-40 disabled:shadow-none dark:text-slate-950"
          disabled={busy || !text.trim()}
          onClick={() => void start({ text })}
        >
          {busy ? <><Loader2 size={18} className="animate-spin" /> Starting…</> : <><Wand2 size={18} /> Compose my process</>}
        </button>

        <ReplayPicker onStarted={onStarted} />
      </div>
    </div>
  );
}
