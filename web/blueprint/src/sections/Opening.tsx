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
          <p className="subhead">And what I think actually does.</p>
        </div>

        <div className="stack-lg">
          <p className="lede">
            You&apos;ve sponsored the work, the demos went fine, contracts
            were signed, things shipped. Then the next initiative arrives and
            effectively starts over with new tech, new prompts, new
            evaluation, new integrations, a fresh six-week clock, often a
            different vendor. By the time the next initiative starts, very
            little of what the previous one built is still doing useful work.
          </p>

          <p className="lede">
            Two reasons. The first is that humans cannot realistically build,
            train and govern AI initiatives one-by-one fast enough to keep up.
            The use-case surface is too wide; the implement → train → onboard →
            change loop is too slow. By the time the first one lands, the rest
            of the organisation has adopted three other tools.
          </p>

          <p className="lede">
            The second reason is less commonly named. Most organisations are
            running several different frameworks for building agents at the
            same time. None of them strengthen each other. Every team picks
            its own, every implementation is a private effort, and nothing
            accumulates, because none of the implementations share a
            foundation that would let them.
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
