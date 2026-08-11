export function Opening() {
  return (
    <section className="section opening">
      <div className="column--wide">
        <div className="opening__headline-block">
          <h1 className="headline">
            <em>See what an agentic organisation</em>
            <br />
            actually looks like.
          </h1>
          <p className="subhead">And use the blueprint to build yours.</p>
        </div>

        <div className="stack-lg">
          <p className="lede">
            Most demos show one assistant handling one task. They don&apos;t
            show specialised agents and people working across functions,
            sharing systems, waiting on decisions, recovering from failures,
            and governed as one workforce. That gap is where agentic
            strategies stall.
          </p>

          <p className="lede">
            Initiatives restart because each pilot rebuilds orchestration,
            prompts, evaluation, integrations, policy and observability from
            scratch. By the time the second one lands, the first is already
            diverging. Nothing accumulates across the organisation.
          </p>

          <p className="lede">
            Zava is a working reference implementation of an agentic
            organisation. A complete synthetic organisation makes the
            pattern portable: the same boundaries connect systems, skills,
            MCPs, policies, data and people — whether the organisation is
            synthetic today or real tomorrow.
          </p>
        </div>

        <div className="opening__pullquote-block">
          <p className="pullquote">
            Each of these initiatives is a hand-copied manuscript. The thing
            missing from the picture is a printing press.
          </p>
        </div>
      </div>
    </section>
  );
}
