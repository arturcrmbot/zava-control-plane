import TelcoWorld from "@client/routes/TelcoWorld";
import { useWorldSimulation } from "@client/hooks/useWorldSimulation";

export default function TelcoWorldRoute() {
  const simulation = useWorldSimulation();
  return (
    <TelcoWorld
      state={simulation.state}
      events={simulation.events}
      loading={simulation.loading}
      error={simulation.error}
      onFailSite={simulation.injectSiteFailure}
    />
  );
}
