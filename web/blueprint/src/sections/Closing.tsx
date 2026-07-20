import { getDemoUrl } from "../lib/useDemoUrl";
import { BOOKING_URL, ZAVA_CONSTELLATION_URL } from "../lib/links";

export function Closing() {
  return (
    <section className="section closing">
      <div className="column--wide stack-lg">
        <p className="subtitle">In closing</p>

        <p className="body">
          What we hand over is a working organisation: the decision-makers
          are mapped, approvals route through one matrix, and nine
          workflows are already wired into the substrate with more being
          composed.
        </p>

        <p className="body">
          The workflows currently run against synthetic data and stubbed
          MCPs, so they&apos;re effectively placeholders. The substrate
          around them is real: identity, audit, the policy file, the
          validators, the agent harness, the design-time skills that build
          the next skill. That part stays in place when you swap the stubs
          for your real Workday, SAP, Salesforce and Mediaocean.
        </p>

        <p className="body">
          We hand it over as it stands today. Then a week with you, working
          out your real ambition (one workflow or fifty), and getting one
          of those workflows running against your real systems before we
          leave.
        </p>

        <p className="closing__final">
          The interesting question is no longer which AI project to fund
          next, but what an organisation looks like once it&apos;s wired
          into something like this and allowed to extend itself.
        </p>

        <p className="body" style={{ color: "var(--ink-mute)" }}>
          That is what I&apos;d like you to consider backing.
        </p>

        <ul className="closing__cta-list">
          <li>
            <a
              href={BOOKING_URL}
              className="closing__cta"
              rel="noopener noreferrer"
              target="_blank"
            >
              Let&apos;s talk →
            </a>
            <span className="closing__cta-note">
              Half an hour, no slides. I&apos;ll walk through your
              ambition and what it would take to stand a substrate of
              your own up.
            </span>
          </li>
          <li>
            <a
              href={getDemoUrl("closing")}
              className="closing__cta"
              rel="noopener noreferrer"
              target="_blank"
            >
              Watch it run →
            </a>
            <span className="closing__cta-note">
              The control plane is deployed at a public URL, replaying
              workflows that previously executed against the substrate
              with synthetic data and stubbed external systems.
            </span>
          </li>
          <li>
            <a
              href={ZAVA_CONSTELLATION_URL}
              className="closing__cta"
              rel="noopener noreferrer"
              target="_blank"
            >
              Build this for your own organisation →
            </a>
            <span className="closing__cta-note">
              <code className="mono">compose-org</code> researches, designs,
              builds and proves an executable vertical for your workflow.{" "}
              <code className="mono">zava-workspace-deploy</code> publishes
              it as private-live or public-replay.
            </span>
          </li>
        </ul>
      </div>
    </section>
  );
}
