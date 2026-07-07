import { useEffect, useState } from "react";
import { PlayCircle } from "lucide-react";
import { listTapes, startReplay } from "./api";

export function ReplayPicker({ onStarted }: { onStarted: (cid: string) => void }) {
  const [tapes, setTapes] = useState<string[]>([]);
  const [tape, setTape] = useState("");
  const [handsFree, setHandsFree] = useState(true);

  useEffect(() => { void listTapes().then((t) => { setTapes(t); if (t[0]) setTape(t[0]); }); }, []);
  if (tapes.length === 0) return null;

  return (
    <div className="mt-8 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 p-4">
      <p className="text-sm font-medium text-slate-900 dark:text-slate-300">Replay a recorded compose (demo-safe)</p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <select className="rounded-md bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 px-3 py-1.5 text-sm text-slate-900 dark:text-slate-100" value={tape} onChange={(e) => setTape(e.target.value)}>
          {tapes.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
          <input type="checkbox" checked={handsFree} onChange={(e) => setHandsFree(e.target.checked)} />
          Hands-free (uncheck to click through questions)
        </label>
        <button className="flex items-center gap-2 rounded-md bg-violet-600 hover:bg-violet-500 px-3 py-1.5 text-sm font-medium text-white"
          onClick={() => void startReplay({ tape, speed: 8, pause_on_hitl: !handsFree }).then(onStarted)}>
          <PlayCircle size={16} /> Replay
        </button>
      </div>
    </div>
  );
}
