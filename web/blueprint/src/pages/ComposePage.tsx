import { useState } from "react";
import { IntakePanel } from "./compose/IntakePanel";
import { Cockpit } from "./compose/Cockpit";

export function ComposePage() {
  const [cid, setCid] = useState<string | null>(null);
  return cid ? <Cockpit cid={cid} /> : <IntakePanel onStarted={setCid} />;
}
