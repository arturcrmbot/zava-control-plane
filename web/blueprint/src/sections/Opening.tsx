export function Opening() {
  return (
    <section className="section opening">
      <div className="column--wide">
        <div className="opening__headline-block">
          <h1 className="headline">
            <em>Why your agentic strategy</em>
            <br />
            isn&apos;t moving the needle.
          </h1>
          <p className="subhead">And what we think actually does.</p>
        </div>

        <div className="column stack-lg">
          <p className="lede">
            You&apos;ve sponsored the work. Demos went fine. Contracts signed.
            Things shipped. Then the next initiative arrived and effectively
            started over: new tech, new prompts, new evaluation, new
            integrations, fresh six-week clock, often a different vendor. The
            value stops compounding about a week after each contract ends.
          </p>

          <p className="lede">
            Two reasons. The first is that humans cannot realistically build,
            train and govern AI initiatives one-by-one fast enough to keep up.
            The use-case surface is too wide; the implement → train → onboard →
            change loop is too slow. By the time the first one lands, the rest
            of the organisation has adopted three other tools.
          </p>

          <p className="lede">
            The second is more controversial. Most organisations are running
            several different frameworks for building agents at the same time.
            None of them strengthen each other. Every team picks its own; every
            implementation is a private effort; nothing accumulates because
            nothing is allowed to share a foundation.
          </p>
        </div>

        <div className="opening__pullquote-block">
          <p className="pullquote">
            What you&apos;ve been buying is manuscript after manuscript after
            manuscript. What you need is a press.
          </p>
        </div>
      </div>
    </section>
  );
}
