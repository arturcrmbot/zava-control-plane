// web/blueprint/src/features/governance/OwaspCoverageCard.tsx
//
// Phase 8 TASK-060 of plan/feature-agent-governance-toolkit-1.md.
//
// Microsite component that surfaces the live AGT verify report as the
// OWASP Agentic AI Top 10 coverage card. Consumes the agt-evidence.json
// artifact published by .github/workflows/agt-governance.yml (TASK-059).
//
// Lookup order for the evidence file:
//   1. /agt-evidence.json (relative — published by the deploy alongside
//      the static bundle).
//   2. ./agt-evidence.json (same).
//   3. import.meta.env.VITE_AGT_EVIDENCE_URL — explicit override.
//
// Renders the 10 ASI rows with ✓/✗ from agt-verify.controls. If the
// file isn't reachable, renders a graceful "evidence not yet published"
// state so the page never breaks.
import { useEffect, useState } from "react";

type Control = {
  id: string;
  name: string;
  present: boolean;
  module?: string;
  component?: string;
  error?: string | null;
};

type VerifyReport = {
  passed: boolean;
  coverage_pct: number;
  controls_passed: number;
  controls_total: number;
  toolkit_version: string;
  verified_at: string;
  attestation_hash: string;
  controls: Control[];
};

type Evidence = {
  schema: string;
  generated_at: string;
  git_sha?: string;
  reports: {
    "agt-verify"?: VerifyReport;
    "agt-doctor"?: { healthy?: boolean };
  };
};

const CANDIDATE_URLS = [
  // @ts-ignore - env declared by Vite at build time
  (import.meta as any).env?.VITE_AGT_EVIDENCE_URL,
  "/agt-evidence.json",
  "./agt-evidence.json",
].filter(Boolean) as string[];

async function fetchEvidence(): Promise<Evidence | null> {
  for (const url of CANDIDATE_URLS) {
    try {
      const r = await fetch(url);
      if (r.ok) {
        return (await r.json()) as Evidence;
      }
    } catch {
      // try the next candidate
    }
  }
  return null;
}

export default function OwaspCoverageCard() {
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchEvidence().then((e) => {
      if (!cancelled) {
        setEvidence(e);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <section className="rounded-lg border border-zinc-200 bg-white p-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-700">
          OWASP Agentic AI Top 10
        </h3>
        <p className="mt-2 text-sm text-zinc-500">Loading evidence…</p>
      </section>
    );
  }

  const verify = evidence?.reports?.["agt-verify"];
  if (!evidence || !verify) {
    return (
      <section className="rounded-lg border border-zinc-200 bg-white p-4">
        <div className="flex items-baseline justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-700">
            OWASP Agentic AI Top 10
          </h3>
          <span className="text-xs text-zinc-400">evidence not yet published</span>
        </div>
        <p className="mt-2 text-sm text-zinc-600">
          The CI ring at{" "}
          <code className="font-mono text-xs">
            .github/workflows/agt-governance.yml
          </code>{" "}
          publishes a fresh{" "}
          <code className="font-mono text-xs">agt-evidence.json</code> on every
          push to main. Pull a recent build's artifact to render this card
          locally, or set{" "}
          <code className="font-mono text-xs">VITE_AGT_EVIDENCE_URL</code>{" "}
          at build time to a stable URL.
        </p>
      </section>
    );
  }

  const allGreen = verify.passed && verify.coverage_pct === 100;

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-700">
          OWASP Agentic AI Top 10
        </h3>
        <span
          className={`text-xs font-semibold ${
            allGreen ? "text-emerald-700" : "text-rose-700"
          }`}
        >
          {verify.controls_passed}/{verify.controls_total} covered
        </span>
      </div>

      <ul className="mt-3 space-y-1 text-sm">
        {verify.controls.map((c) => (
          <li
            key={c.id}
            className={`flex items-baseline justify-between rounded px-2 py-1 ${
              c.present ? "bg-emerald-50" : "bg-rose-50"
            }`}
          >
            <span className="flex items-baseline gap-2">
              <span className="font-mono text-xs text-zinc-500">{c.id}</span>
              <span className="text-zinc-800">{c.name}</span>
            </span>
            <span
              className={`font-mono text-sm ${
                c.present ? "text-emerald-700" : "text-rose-700"
              }`}
              title={
                c.present
                  ? `${c.module ?? ""} :: ${c.component ?? ""}`
                  : c.error ?? "missing"
              }
            >
              {c.present ? "✓" : "✗"}
            </span>
          </li>
        ))}
      </ul>

      <dl className="mt-3 grid grid-cols-2 gap-x-2 gap-y-0.5 border-t border-zinc-100 pt-2 text-[11px] text-zinc-500">
        <dt>toolkit</dt>
        <dd className="font-mono text-zinc-700">{verify.toolkit_version}</dd>
        <dt>verified at</dt>
        <dd className="font-mono text-zinc-700">{verify.verified_at}</dd>
        <dt>attestation</dt>
        <dd className="truncate font-mono text-zinc-700">
          {verify.attestation_hash.slice(0, 16)}…
        </dd>
        {evidence.git_sha && (
          <>
            <dt>git sha</dt>
            <dd className="font-mono text-zinc-700">
              {evidence.git_sha.slice(0, 12)}
            </dd>
          </>
        )}
      </dl>
    </section>
  );
}
