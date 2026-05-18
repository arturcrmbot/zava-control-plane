// web/client/components/feed/DrawerDecision.tsx
import type { DrawerData } from "./Drawer";
import type { RolePreset } from "@shared/roles";
export default function DrawerDecision(_props: {
  data: DrawerData; role: RolePreset; onRefresh: () => Promise<void> | void;
}) {
  return <section><h2>Decision</h2></section>;
}
