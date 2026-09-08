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
            Most demos stop at one assistant handling one task. They rarely
            show what happens when specialised agents and people work across
            functions, share systems, wait for decisions and recover from
            failures under one set of controls. That is where an agent demo
            has to become an operating model.
          </p>

          <p className="lede">
            Too many pilots rebuild orchestration, prompts, evaluation,
            integrations, policy and observability from scratch. By the time
            the second lands, the first has already diverged. The organisation
            pays for the same foundations again.
          </p>

          <p className="lede">
            Zava is a working reference implementation of an agentic
            organisation. A complete synthetic organisation makes the
            reference portable without pretending that mock records are a
            customer estate. Its runtime boundaries are executable. Customers
            can replace those boundaries one at a time with their systems,
            data, policies and people.
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
