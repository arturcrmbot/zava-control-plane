import { CompoundingDiagram } from "../components/CompoundingDiagram";

const COMPOSITION_STEPS = ["Research", "Design", "Build", "Prove"];

export function MetaSkill() {
  return (
    <section className="section meta">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">How the type case extends itself</p>
          <h2 className="section-title">
            Each new domain is mostly built from what&apos;s already cast.
          </h2>
          <p className="body">
            The first domain pays the full price because every skill is new.
            The second mostly recomposes what the first one cast, the third
            is largely reuse, and by the fourth or fifth most of the
            remaining work is orchestrator code over a substrate that&apos;s
            already there. The cumulative curve below is drawn live from the
            codebase, not projected.
          </p>
        </header>

        <CompoundingDiagram />

        <div className="meta__extension">
          <div className="meta__extension-text">
            <h3 className="passage-title">Two public steps, one executable org.</h3>
            <p className="body">
              <strong>compose-org</strong> is a guided pipeline that walks{" "}
              {COMPOSITION_STEPS.join(" → ")}. Research is source-backed —
              drawn from the org&apos;s public footprint — but the actor world
              it produces is fully synthetic and causal: every entity, sensor,
              and objective is generated, not scraped. <strong>zava-workspace-deploy</strong>{" "}
              takes that proven output and requires an explicit choice:
              private-live (a live simulation running against real Azure infra)
              or public-replay (a deterministic tape anyone can watch without
              touching live systems). The two modes share one codebase; the
              choice is a deploy-time flag. See{" "}
              <a
                className="footer__link"
                href="https://aiappsgbb.github.io/zava-constellation/"
                target="_blank"
                rel="noopener noreferrer"
              >
                zava-constellation
              </a>
              {" "}for the companion skill library.
            </p>
          </div>

          <aside className="meta__sidebar">
            <div className="meta__sidebar-title">compose-org pipeline</div>
            <div className="meta__sidebar-list">
              {COMPOSITION_STEPS.join(" → ")}
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
}
