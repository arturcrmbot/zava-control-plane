import { useState } from "react";
import { Rocket, Loader2, PartyPopper, CheckCircle2 } from "lucide-react";
import { pollComposition } from "./api";

const VITE_PORTS = new Set(["5273", "5274", "5275"]);
function constellationUrl(): string {
  const fromEnv = (import.meta.env.VITE_BLUEPRINT_URL as string | undefined)?.trim();
  if (fromEnv) return `${fromEnv.replace(/\/$/, "")}/?view=constellation&from=fleet`;
  if (typeof window !== "undefined" && VITE_PORTS.has(window.location.port)) {
    return `${window.location.protocol}//${window.location.hostname}:5275/?view=constellation&from=fleet`;
  }
  return "/blueprint/?view=constellation&from=fleet";
}

export function IgniteButton({
  done, onIgnite,
}: {
  done: { workflow_type: string; display_name: string };
  onIgnite: () => Promise<void>;
}) {
  const [phase, setPhase] = useState<"idle" | "rearming" | "live">("idle");

  async function go() {
    setPhase("rearming");
    await onIgnite();
    const live = await pollComposition(done.workflow_type);
    setPhase("live");
    if (live) {
      const url = `${constellationUrl()}&highlight=${encodeURIComponent(done.workflow_type)}`;
      window.open(url, "_blank");
    }
  }

  return (
    <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-2xl dark:border-slate-700 dark:bg-slate-900">
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-emerald-50 dark:bg-emerald-950/40">
        {phase === "live" ? (
          <PartyPopper size={24} className="text-emerald-600 dark:text-emerald-400" />
        ) : phase === "rearming" ? (
          <Loader2 size={24} className="animate-spin text-emerald-600 dark:text-emerald-400" />
        ) : (
          <CheckCircle2 size={24} className="text-emerald-600 dark:text-emerald-400" />
        )}
      </div>

      <h3 className="mt-3 text-[17px] font-bold tracking-tight text-slate-900 dark:text-slate-100">
        {phase === "live" ? "You're live!" : phase === "rearming" ? "Bringing your process online…" : "Your process is ready"}
      </h3>
      <p className="mx-auto mt-1 max-w-xs text-[13px] leading-relaxed text-slate-500 dark:text-slate-400">
        {phase === "live"
          ? `“${done.display_name}” is now running. Opening it in your live process view.`
          : phase === "rearming"
          ? "This takes a moment while I switch it on."
          : `I'll switch on “${done.display_name}” and open it in your live process view.`}
      </p>

      {phase === "idle" && (
        <button
          onClick={go}
          className="mt-4 inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-6 py-3 text-[15px] font-semibold text-white shadow-lg shadow-emerald-600/20 hover:bg-emerald-500"
        >
          <Rocket size={18} /> Go live
        </button>
      )}
    </div>
  );
}
