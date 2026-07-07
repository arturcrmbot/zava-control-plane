import { useEffect, useState } from "react";
import { IntakePanel } from "@client/components/compose/IntakePanel";
import { StudioCockpit } from "@client/components/compose/studio/StudioCockpit";
import { StudioPreview } from "@client/components/compose/studio/StudioPreview";
import { startReplay } from "@client/components/compose/api";

export default function Compose() {
  const [cid, setCid] = useState<string | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const params = new URLSearchParams(window.location.search);

  useEffect(() => {
    const tape = params.get("replay");
    const pause = params.has("pause");
    if (tape) void startReplay({ tape, speed: 8, pause_on_hitl: pause }).then(setCid);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (params.has("preview")) return <StudioPreview />;
  if (cid) return <StudioCockpit cid={cid} source={source} replay={params.has("replay")} />;
  return <IntakePanel onStarted={(id, src) => { setSource(src ?? null); setCid(id); }} />;
}
