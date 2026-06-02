/**
 * Section 3 — The flag-plant.
 *
 * Reframes everything that follows: this isn't an essay about substrate
 * components, it's a demonstration of a simulated organisation that runs
 * itself. The architecture sections after this are "how", not "what".
 */
export function Vision() {
  return (
    <section className="section vision">
      <div className="column--wide stack-lg">
        <p className="subtitle">What I built</p>
        <h2 className="section-title">
          A simulated organisation that runs itself.
        </h2>
        <p className="body">
          The substrate runs a simulated organisation. Nine workflows are
          wired into it end-to-end today, with dozens of personas
          approving and escalating decisions, a delegated-authority
          matrix that compliance can edit directly, and a shared memory
          the agents read from and add to overnight.
        </p>
        <p className="body">
          It is a model of what a company looks like once enough of its
          routine decisions are made by agents operating under one set
          of rules and one audit trail.
        </p>
      </div>
    </section>
  );
}
