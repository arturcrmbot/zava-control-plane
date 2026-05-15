import { CompoundingDiagram } from "../components/CompoundingDiagram";

const DESIGN_TIME_SKILLS = ["brainstorming", "humanizer", "writing-plans"];

export function MetaSkill() {
  return (
    <section className="section meta">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">How the type case extends itself</p>
          <h2 className="section-title">
            <em>Each new domain is mostly built from what&apos;s already cast.</em>
          </h2>
          <p className="body">
            The first domain pays the full price — every skill is new. The
            second mostly recomposes what the first one cast. The third is
            mostly reuse. The cumulative curve below is drawn live from the
            codebase, not projected. By the third domain most of the case is
            already cast; the fourth and fifth are mostly orchestrator code
            over a substrate that&apos;s already there.
          </p>
        </header>

        <CompoundingDiagram />

        <div className="meta__extension">
          <div className="meta__extension-text">
            <h3 className="passage-title">The skills that author skills.</h3>
            <p className="body">
              You start from our template, which ships with a skill-builder
              skill. You watch it build the first domains. As it goes, you feed
              it business context — your policies, your data, your edge cases.
              Very quickly, you notice it&apos;s doing the work end-to-end. By
              then it knows enough about you to do so without your help.
            </p>
            <p className="body">
              This is why we said earlier that the substrate has to be the
              substrate. The skill-builder learns from every implementation it
              builds against the same primitives — the same identity, the same
              audit ledger, the same MCPs. That loop only closes inside one
              substrate. Drop a third-party agent in alongside it and the loop
              breaks: there&apos;s no shared foundation for it to learn
              against.
            </p>
          </div>

          <aside className="meta__sidebar">
            <div className="meta__sidebar-title">Spec produced at design time</div>
            <div className="meta__sidebar-list">
              {DESIGN_TIME_SKILLS.join(" · ")}
            </div>
            <p>
              Used by the agent that talks to the customer (this Copilot
              session, in fact). Lives outside the customer environment.
              Already built — this is how we build the runtime skills above.
            </p>
          </aside>
        </div>
      </div>
    </section>
  );
}
