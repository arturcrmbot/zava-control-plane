import { useState } from "react";
import { Rocket } from "lucide-react";
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
  if (phase === "rearming")
    return <div className="text-sm text-amber-700 dark:text-amber-300">Re-arming the substrate…</div>;
  return (
    <button onClick={go}
      className="flex items-center gap-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-5 py-3 text-base font-semibold text-white shadow-lg">
      <Rocket size={18} /> Ignite "{done.display_name}"
    </button>
  );
}
