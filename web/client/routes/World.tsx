import SupportWorld from "@client/routes/SupportWorld";
import TelcoWorldRoute from "@client/routes/TelcoWorldRoute";
import { useRuntimeManifest } from "@client/hooks/useRuntimeManifest";

export default function World() {
  const { manifest, loading, error } = useRuntimeManifest();
  if (loading) return <div role="status">Loading runtime…</div>;
  if (error || !manifest) {
    return <div role="alert">{error ?? "Runtime unavailable"}</div>;
  }
  if (manifest.world === null) {
    return (
      <div role="status">
        No actor world is active for {manifest.vertical.display_name}.
      </div>
    );
  }
  return manifest.ui.lenses.includes("telco-network")
    ? <TelcoWorldRoute />
    : <SupportWorld />;
}
