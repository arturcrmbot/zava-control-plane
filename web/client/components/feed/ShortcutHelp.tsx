// web/client/components/feed/ShortcutHelp.tsx
//
// Overlay listing all keyboard shortcuts. Triggered by `?` (or by clicking
// the help affordance in the header — not added in v1).
import { X } from "lucide-react";

const ROWS: Array<{ keys: string[]; label: string }> = [
  { keys: ["j"],      label: "Next card" },
  { keys: ["k"],      label: "Previous card" },
  { keys: ["Enter"],  label: "Open focused card in drawer" },
  { keys: ["/"],      label: "Focus the search box" },
  { keys: ["Esc"],    label: "Close drawer / shortcut help" },
  { keys: ["?"],      label: "Toggle this help" },
];

export default function ShortcutHelp({ onClose }: { onClose: () => void }) {
  return (
    <div
      role="dialog"
      aria-label="Keyboard shortcuts"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg shadow-xl max-w-md w-full mx-4 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Keyboard shortcuts</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 dark:text-slate-500 dark:hover:text-slate-100 dark:hover:bg-slate-800"
          ><X size={16} /></button>
        </header>
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {ROWS.map((r) => (
            <li key={r.label} className="flex items-center justify-between px-4 py-2.5 text-sm">
              <span className="text-slate-700 dark:text-slate-200">{r.label}</span>
              <span className="flex gap-1">
                {r.keys.map((k) => (
                  <kbd
                    key={k}
                    className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-600 text-xs font-mono"
                  >{k}</kbd>
                ))}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
