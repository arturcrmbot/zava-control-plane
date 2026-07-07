import { useState } from "react";
import { Rocket } from "lucide-react";
import { pollComposition } from "./api";

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
      window.location.href = `/?view=constellation&highlight=${encodeURIComponent(done.workflow_type)}`;
    }
  }
  if (phase === "rearming")
    return <div className="text-sm text-amber-300">Re-arming the substrate…</div>;
  return (
    <button onClick={go}
      className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-3 text-base font-semibold text-white shadow-lg hover:bg-emerald-500">
      <Rocket size={18} /> Ignite "{done.display_name}"
    </button>
  );
}
