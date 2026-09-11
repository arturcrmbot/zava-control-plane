import { buildConstellationUrl } from "../lib/constellationUrl";
import { getDemoUrl } from "../lib/useDemoUrl";
import { CONTROL_PLANE_REPO_URL } from "../lib/links";
import walkthroughUrl from "../../../../docs/media/aurora-recorded-walkthrough.mp4";
import walkthroughPoster from "../../../../docs/media/aurora-recorded-walkthrough-poster.jpg";
import walkthroughCaptions from "../../../../docs/media/aurora-recorded-walkthrough.vtt?url";
import walkthroughProvenance from "../../../../docs/media/aurora-recorded-walkthrough.provenance.json?url";

export function Opening() {
  const demonstration = buildConstellationUrl(
    typeof window !== "undefined" ? window.location.href : CONTROL_PLANE_REPO_URL,
    getDemoUrl("opening"),
  );
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

        <div className="opening__actions">
          <a className="opening__action opening__action--primary" href={demonstration} target="_blank" rel="noopener noreferrer">
            Open recorded demonstration
          </a>
          <a className="opening__action" href={`${CONTROL_PLANE_REPO_URL}/blob/main/docs/zava-hosting-brief.md`} target="_blank" rel="noopener noreferrer">
            Run the reference
          </a>
        </div>

        <figure className="opening__film">
          <video controls preload="metadata" poster={walkthroughPoster} aria-label="Recorded Aurora development walkthrough">
            <source src={walkthroughUrl} type="video/mp4" />
            <track kind="captions" srcLang="en" label="English" src={walkthroughCaptions} default />
          </video>
          <figcaption>
            Development walkthrough · 1:42. Actual local execution, synthetic
            business data, automated operator exercise.{" "}
            <a href={walkthroughProvenance} target="_blank" rel="noopener noreferrer">Source and limits</a>
          </figcaption>
        </figure>

        <div className="stack-lg">
          <p className="lede">
            Most demos stop at one assistant handling one task. The harder
            problem is connecting work across teams: one spending decision
            changes what happens to invoices, people retain authority, and
            everyone can see why an action was taken.
          </p>

          <p className="lede">
            Follow Aurora&apos;s budget signal through an agent recommendation,
            CFO approval, a governed policy and queued invoice reviews.
            The point is reuse. Each new process should not need its own
            integration stack, approval machinery and audit trail.
          </p>

          <p className="lede">
            Zava is a working reference implementation of an agentic
            organisation, not a packaged production platform. A complete synthetic organisation
            makes it portable without customer data. Keep your existing agents
            and workflows; connect your systems, policies and people at the
            demonstrated boundaries.
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
