export function Closing() {
  const DEMO_URL = ((import.meta as any).env?.VITE_DEMO_URL as string | undefined)
    ?? "https://zava-zava-verify.wonderfulocean-b02d74da.swedencentral.azurecontainerapps.io/?from=essay";

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
          Each subsequent piece of work is cheaper because the shape is
          already in place and you&apos;re composing on top of it.
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
          That is what we&apos;d like you to consider backing.
        </p>

        <p className="body">
          <a
            href={`${DEMO_URL}${DEMO_URL.includes("?") ? "&" : "?"}from=essay`}
            className="closing__cta"
            rel="noopener noreferrer"
            target="_blank"
          >
            Watch it run →
          </a>
        </p>
      </div>
    </section>
  );
}
