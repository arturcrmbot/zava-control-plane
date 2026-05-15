import { CompoundingDiagram } from "../components/CompoundingDiagram";

const DESIGN_TIME_SKILLS = ["brainstorming", "humanizer", "writing-plans", "compose-domain", "compose-persona"];

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
            The first domain pays the full price. Every skill is new. The
            second mostly recomposes what the first one cast. The third is
            mostly reuse. The cumulative curve below is drawn live from the
            codebase, not projected. By the third domain most of the case is
            already cast. The fourth and fifth are mostly orchestrator code
            over a substrate that&apos;s already there.
          </p>
        </header>

        <CompoundingDiagram />

        <div className="meta__extension">
          <div className="meta__extension-text">
            <h3 className="passage-title">The skills that author skills.</h3>
            <p className="body">
              The substrate ships with a small library of design-time skills
              (
              <a
                className="footer__link"
                href="https://github.com/arturcrmbot/zava-design-skills"
                target="_blank"
                rel="noopener noreferrer"
              >
                zava-design-skills
              </a>
              ) that an agent uses while it&apos;s building the runtime
              skills above. Brainstorming turns a brief into a structured
              spec.{" "}
              <code className="mono">writing-plans</code> turns the spec
              into a numbered implementation plan.{" "}
              <code className="mono">compose-domain</code> and{" "}
              <code className="mono">compose-persona</code> scaffold a new
              workflow or a new approver from that plan. Humanizer cleans
              up the prose so the result doesn&apos;t read like a model
              wrote it.
            </p>
            <p className="body">
              This Copilot session is using those skills right now, while
              we build out the article you&apos;re reading. The same
              skill library is what we use to build the runtime skills.
              And it&apos;s what your team uses to extend the substrate
              after we leave.
            </p>
            <p className="body">
              The skill-builder learns from every implementation it builds
              against the same primitives. The same identity, the same
              audit ledger, the same MCPs. That loop only closes inside one
              substrate. Drop a third-party agent in alongside it and the
              loop breaks. There&apos;s no shared foundation for it to
              learn against.
            </p>
          </div>

          <aside className="meta__sidebar">
            <div className="meta__sidebar-title">Design-time skills</div>
            <div className="meta__sidebar-list">
              {DESIGN_TIME_SKILLS.join(" · ")}
            </div>
            <p>
              Used by the agent that talks to the customer (this Copilot
              session, in fact). Lives outside the customer environment.
              Already built. This is how we build the runtime skills above.
            </p>
          </aside>
        </div>
      </div>
    </section>
  );
}
