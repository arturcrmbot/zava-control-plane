import { useComposition } from "../lib/useComposition";
import { CompositionMap } from "../components/CompositionMap";

export function Composition() {
  const { data } = useComposition();

  return (
    <section className="section composition">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">Inside a working pack</p>
          <h2 className="section-title">
            The Agency pack is the worked example on this page.
          </h2>
          <p className="body">
            The {data.vertical.display_name} pack is the worked example used
            throughout this article. Its specialised skills, pack-scoped MCP
            adapters, durable workflows, personae and governance run through
            one control plane. The code is executable. Organisational records
            and external systems are synthetic so the reference can run
            without a customer estate behind it.
          </p>
          <p className="body">
            The map below is a curated static Agency snapshot bundled with
            the article. It is not live inventory or evidence of proof status.
            It shows how that pack combines skills, tools and domains.
          </p>
          <p className="body">
            Tap or hover any tile to see what each workflow composes.
          </p>
        </header>

        <CompositionMap data={data} />

        <p className="body">
          A workflow&apos;s phases don&apos;t each get their own agent.
          Adjacent phases that share an approval boundary collapse into a
          single segment, so a ten-phase workflow might run as six
          segments with a human checkpoint between them. Inside a single segment
          the model decides which skill to call next; the orchestrator
          decides segment order, approval gates and retries.
        </p>
      </div>
    </section>
  );
}
