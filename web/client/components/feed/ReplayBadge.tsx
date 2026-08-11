import { useState } from "react";
import { useReplayMeta } from "@client/hooks/useReplayMeta";

function formatRecorded(iso?: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function formatVertical(vertical?: string): string {
  if (!vertical) return "Unavailable";
  return vertical
    .split(/[-_]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function ReplayBadge() {
  const meta = useReplayMeta();
  const [open, setOpen] = useState(false);

  if (!meta || meta.mode !== "replay") return null;

  const date = formatRecorded(meta.recorded_at);
  const selectedVertical = formatVertical(meta.selected_vertical);
  const activeVertical = formatVertical(meta.active_vertical);
  const label = ["Recorded replay", selectedVertical, date].filter(Boolean).join(" · ");

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 rounded border border-amber-500/40 bg-amber-500/10 px-2 py-1 text-xs text-amber-700 hover:bg-amber-500/20 dark:text-amber-300"
      >
        <span className="text-amber-500">●</span>
        <span>{label}</span>
      </button>
      {open && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setOpen(false)}
        >
          <div
            className="max-w-md space-y-2 rounded bg-white p-4 text-sm dark:bg-slate-900"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 className="text-base font-semibold">You&apos;re watching a replay</h2>
            <p>
              This is recorded execution. The buttons you see are real but disabled,
              so clicking them does nothing.
            </p>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
              <dt className="font-medium">Selected vertical</dt>
              <dd>{selectedVertical}</dd>
              <dt className="font-medium">Recording date</dt>
              <dd>{date || "Unavailable"}</dd>
            </dl>
            {meta.pack_matches_tape === false && (
              <p
                role="alert"
                className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-amber-800 dark:text-amber-200"
              >
                This tape was recorded for {selectedVertical}. The running pack is{" "}
                {activeVertical}, so this replay is not presented as current for either pack.
              </p>
            )}
            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded bg-slate-200 px-3 py-1 text-xs hover:opacity-80 dark:bg-slate-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
