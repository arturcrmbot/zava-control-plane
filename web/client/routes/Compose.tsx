import { useEffect, useState } from "react";
import { IntakePanel } from "@client/components/compose/IntakePanel";
import { Cockpit } from "@client/components/compose/Cockpit";
import { startReplay } from "@client/components/compose/api";

export default function Compose() {
  const [cid, setCid] = useState<string | null>(null);
  useEffect(() => {
    const tape = new URLSearchParams(window.location.search).get("replay");
    if (tape) void startReplay({ tape, speed: 8, pause_on_hitl: false }).then(setCid);
  }, []);
  return cid ? <Cockpit cid={cid} /> : <IntakePanel onStarted={setCid} />;
}
