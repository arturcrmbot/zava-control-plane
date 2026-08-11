import { getDemoUrl } from "../lib/useDemoUrl";
import { buildConstellationUrl } from "../lib/constellationUrl";
import { BOOKING_URL, ZAVA_CONSTELLATION_URL } from "../lib/links";

function getClosingConstellationUrl(): string {
  const href =
    typeof window !== "undefined"
      ? window.location.href
      : "https://placeholder.invalid/";
  return buildConstellationUrl(href, getDemoUrl("closing"));
}

export function Closing() {
  return (
    <section className="section closing">
      <div className="column--wide stack-lg">
        <p className="subtitle">In closing</p>

        <p className="body">
          What is running today is a reference implementation. Governance,
          durable workflows, agent and human boundaries, skills, MCP interfaces
          and audit operate through one control plane. Memory joins that control
          plane only in domains where it is enabled.
        </p>

        <p className="body">
          The public organisation uses synthetic records, personae and external
          systems. Those connection points are part of the reference, not a
          separate simulation phase. Keep your existing agent and workflow
          investments. Connect your existing systems and people, then make its edges real
          one useful journey at a time.
        </p>

        <p className="body">
          Start from the reference, connect one cross-functional journey,
          then expand without rebuilding the shared foundation.
        </p>

        <p className="closing__final">
          The next decision is which parts of your organisation should operate
          as one agentic workforce.
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
              Half an hour, no slides. We&apos;ll walk through your
              ambition and what it would take to stand a reference of your
              own up.
            </span>
          </li>
          <li>
            <a
              href={getClosingConstellationUrl()}
              className="closing__cta"
              rel="noopener noreferrer"
              target="_blank"
            >
              Watch it run →
            </a>
            <span className="closing__cta-note">
              The control plane is deployed at a public URL, replaying
              workflows that previously executed against the substrate
              with synthetic data and external systems.
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
              Use the executable blueprint, then connect your existing
              systems, skills, MCPs, policies, data and people.{" "}
              <code className="mono">compose-org</code> researches, designs,
              builds and proves an executable vertical.{" "}
              <code className="mono">zava-workspace-deploy</code> publishes
              it as private-live or public-replay.
            </span>
          </li>
        </ul>
      </div>
    </section>
  );
}
