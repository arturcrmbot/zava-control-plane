import { useAuthority } from "../lib/useAuthority";
import { AuthorityTable } from "../components/AuthorityTable";

export function Authority() {
  const { data, error, loading } = useAuthority();

  return (
    <section className="section authority">
      <div className="column--wide stack-lg">
        <header className="stack">
          <p className="subtitle">Who is allowed to approve what</p>
          <h2 className="section-title">
            <em>The delegated-authority matrix.</em>
          </h2>
          <p className="body">
            Every approver in the persona library above stops carrying their
            own thresholds. They consult one ordered ruleset — this matrix —
            and get a governing rule id alongside the answer. Editing a limit
            is a JSON edit picked up live; never a code change to the persona.
          </p>
          <p className="body">
            The same matrix backs the agentic side. Every skill that produces
            a HITL routing decision (escalation-advisor, the policy-fit-checker
            for travel, the KYC diligence checker, the access-risk-assessor,
            the renewal-terms-drafter, etc.) calls{" "}
            <code className="mono">delegated_authority_resolve_approver</code>{" "}
            and surfaces the matched rule on its output. The persona then reads{" "}
            <code className="mono">context.authority</code> and proceeds.
          </p>
        </header>

        {loading && <div className="map__placeholder">loading matrix…</div>}
        {error && (
          <div className="map__placeholder map__placeholder--offline">
            Authority matrix is offline.
            <br />
            <span className="mono">
              Start the FastAPI control plane on :3101 to see the live ruleset.
            </span>
          </div>
        )}
        {data && <AuthorityTable data={data} />}
      </div>
    </section>
  );
}
