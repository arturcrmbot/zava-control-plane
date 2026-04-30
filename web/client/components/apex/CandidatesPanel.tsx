// web/client/components/apex/CandidatesPanel.tsx
//
// Admin Candidates panel — Control Plane fallback for delivering magic
// links when ACS Email is unavailable. Lists every active token from the
// MagicLinkStore joined with the candidate name + email; each row has a
// click-to-copy button that puts the full /portal?token=... URL on the
// clipboard so the operator can paste it into a chat / email manually.
//
// Contract: GET /api/portal/admin/links -> { links: Array<{
//   token, candidate_id, scope, issued_at, expires_at,
//   name?, email?, role_id?, workflow_id?
// }> }
//
// See docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Task 13.
import { useEffect, useMemo, useState } from "react";

type LinkRow = {
  token: string;
  candidate_id: string;
  scope: string;
  issued_at: number;
  expires_at: number;
  name?: string | null;
  email?: string | null;
  role_id?: string | null;
  workflow_id?: string | null;
};

const PORTAL_BASE_URL =
  (typeof window !== "undefined" &&
    (window as { __PORTAL_BASE_URL__?: string }).__PORTAL_BASE_URL__) ||
  "http://localhost:5174";

function formatTs(ts: number): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString();
}

function magicLinkUrl(row: LinkRow): string {
  // /portal route consumes status-scope tokens; offer-scope tokens land on
  // an "Open Offer" deep link the candidate clicks from email. Both use
  // the same token in the URL, just different routes.
  const route = row.scope === "offer" ? "offer" : "portal";
  return `${PORTAL_BASE_URL}/${route}?token=${encodeURIComponent(row.token)}`;
}

export default function CandidatesPanel() {
  const [rows, setRows] = useState<LinkRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const refresh = useMemo(
    () => async () => {
      setLoading(true);
      setError(null);
      try {
        const r = await fetch("/api/portal/admin/links");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const body = await r.json();
        setRows(Array.isArray(body.links) ? body.links : []);
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleCopy = async (row: LinkRow) => {
    try {
      await navigator.clipboard.writeText(magicLinkUrl(row));
      setCopiedToken(row.token);
      window.setTimeout(
        () => setCopiedToken((t) => (t === row.token ? null : t)),
        1500,
      );
    } catch {
      // Clipboard API can fail in non-secure contexts; surface the URL inline.
      window.prompt("Copy this link:", magicLinkUrl(row));
    }
  };

  return (
    <div className="panel" data-testid="candidates-panel">
      <div className="panel-header flex items-center justify-between">
        <span>Candidates — magic links</span>
        <button
          type="button"
          onClick={() => void refresh()}
          className="text-xs px-2 py-1 rounded border border-slate-300 hover:bg-slate-100"
        >
          Refresh
        </button>
      </div>
      <div className="panel-body">
        {loading && (
          <div className="text-xs text-slate-500">loading…</div>
        )}
        {error && (
          <div className="text-xs text-rose-600">error: {error}</div>
        )}
        {!loading && !error && rows.length === 0 && (
          <div className="text-xs text-slate-500">
            no active magic links — issue one by completing /apply and triage,
            or via app_state.magic_links.issue() in a REPL.
          </div>
        )}
        {!loading && rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-2 pr-3 font-medium">Name</th>
                  <th className="py-2 pr-3 font-medium">Email</th>
                  <th className="py-2 pr-3 font-medium">Scope</th>
                  <th className="py-2 pr-3 font-medium">Issued</th>
                  <th className="py-2 pr-3 font-medium">Expires</th>
                  <th className="py-2 pr-3 font-medium">Magic link</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.token}
                    className="border-b border-slate-100 last:border-b-0"
                  >
                    <td className="py-2 pr-3">{row.name ?? "—"}</td>
                    <td className="py-2 pr-3 text-slate-600">
                      {row.email ?? "—"}
                    </td>
                    <td className="py-2 pr-3">
                      <span
                        className={`inline-block text-[11px] px-1.5 py-0.5 rounded ${
                          row.scope === "offer"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {row.scope}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-xs text-slate-500">
                      {formatTs(row.issued_at)}
                    </td>
                    <td className="py-2 pr-3 text-xs text-slate-500">
                      {formatTs(row.expires_at)}
                    </td>
                    <td className="py-2 pr-3">
                      <button
                        type="button"
                        onClick={() => void handleCopy(row)}
                        className="text-xs px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-500"
                      >
                        {copiedToken === row.token ? "Copied!" : "Copy link"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
