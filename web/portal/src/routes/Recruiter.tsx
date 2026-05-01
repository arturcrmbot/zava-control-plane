// web/portal/src/routes/Recruiter.tsx
//
// Recruiter view inside the candidate portal — lists every active magic link
// from the MagicLinkStore so an HR/recruiter operator can copy the link to
// any candidate's portal page (status / screen / offer) without digging in
// the email outbox. Used as the demo-day fallback.
//
// Backend contract: GET /api/portal/admin/links → { links: [{
//   token, candidate_id, scope, issued_at, expires_at,
//   name?, email?, role_id?, workflow_id?
// }] }
import { useCallback, useEffect, useState } from "react";
import { getAdminLinks, type AdminLink as LinkRow } from "../lib/api";

const PORTAL_ORIGIN =
  (typeof window !== "undefined" && window.location.origin) ||
  "http://localhost:5174";

function fmtTs(ts: number): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString();
}

function magicLinkUrl(row: LinkRow): string {
  // Same magic-link URL shape Portal.tsx consumes — /portal for status + offer
  // (offer-scope token is just a different scope routed via the same path),
  // /screen for screen-scope.
  const route = row.scope === "screen" ? "screen" : "portal";
  return `${PORTAL_ORIGIN}/${route}?token=${encodeURIComponent(row.token)}`;
}

const SCOPE_CHIP: Record<string, string> = {
  status: "chip-info",
  screen: "chip-success",
  offer:  "chip-warning",
};

export default function Recruiter() {
  const [rows, setRows] = useState<LinkRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const links = await getAdminLinks();
      setRows((prev) => (JSON.stringify(prev) === JSON.stringify(links) ? prev : links));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 8_000);
    return () => window.clearInterval(id);
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
      window.prompt("Copy this link:", magicLinkUrl(row));
    }
  };

  const visible = rows.filter((r) => {
    if (!filter.trim()) return true;
    const f = filter.toLowerCase();
    return (
      (r.name ?? "").toLowerCase().includes(f) ||
      (r.email ?? "").toLowerCase().includes(f) ||
      (r.role_id ?? "").toLowerCase().includes(f) ||
      r.candidate_id.toLowerCase().includes(f) ||
      r.scope.toLowerCase().includes(f)
    );
  });

  const counts = {
    total: rows.length,
    status: rows.filter((r) => r.scope === "status").length,
    screen: rows.filter((r) => r.scope === "screen").length,
    offer:  rows.filter((r) => r.scope === "offer").length,
  };

  return (
    <div className="max-w-6xl mx-auto p-6 sm:p-10 space-y-6">
      <div className="hero">
        <div className="hero-eyebrow">Recruiter view</div>
        <h1 className="hero-title">Candidates &amp; active links</h1>
        <p className="hero-subtitle">
          Every active magic link in the system. Copy any link to manually
          deliver it via Slack, email, or a phone screen — handy when ACS
          Email is rate-limited or when sandboxing the demo.
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Active links" value={counts.total} />
        <Stat label="Status (long-lived)" value={counts.status} tone="info" />
        <Stat label="Screen (single-use)" value={counts.screen} tone="success" />
        <Stat label="Offer (single-use)"  value={counts.offer} tone="warning" />
      </div>

      <div className="panel">
        <div className="panel-header">
          <span>Magic links</span>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter by name / email / role / scope"
              className="form-input !mt-0 text-xs w-72"
            />
            <button
              type="button"
              onClick={() => void refresh()}
              className="btn-secondary"
            >
              Refresh
            </button>
          </div>
        </div>
        <div className="panel-body p-0">
          {loading && (
            <div className="p-6 text-sm text-slate-500 flex items-center gap-2">
              <span className="spinner"/> Loading…
            </div>
          )}
          {error && (
            <div className="p-6 text-sm text-red-700">error: {error}</div>
          )}
          {!loading && !error && visible.length === 0 && (
            <div className="p-6 text-sm text-slate-500">
              {rows.length === 0
                ? "No active magic links yet — submit an application via /apply to spin one up."
                : "No matches. Clear the filter to see all links."}
            </div>
          )}
          {!loading && visible.length > 0 && (
            <div className="overflow-x-auto">
              <table className="table-base">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Scope</th>
                    <th>Issued</th>
                    <th>Expires</th>
                    <th className="text-right">Magic link</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((row) => (
                    <tr key={row.token}>
                      <td className="font-medium text-slate-900">{row.name ?? "—"}</td>
                      <td className="text-slate-600 text-xs">{row.email ?? "—"}</td>
                      <td className="text-xs">{row.role_id ?? "—"}</td>
                      <td>
                        <span className={SCOPE_CHIP[row.scope] ?? "chip-neutral"}>
                          {row.scope}
                        </span>
                      </td>
                      <td className="text-xs text-slate-500">{fmtTs(row.issued_at)}</td>
                      <td className="text-xs text-slate-500">{fmtTs(row.expires_at)}</td>
                      <td className="text-right">
                        <button
                          type="button"
                          onClick={() => void handleCopy(row)}
                          className="btn-secondary"
                        >
                          {copiedToken === row.token ? "✓ Copied" : "Copy link"}
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

      <p className="text-xs text-slate-500 text-center">
        Auto-refreshes every 8 seconds. List backed by{" "}
        <code className="bg-slate-100 px-1.5 py-0.5 rounded">/api/portal/admin/links</code>.
      </p>
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "info" | "success" | "warning";
}) {
  const ringClass =
    tone === "info" ? "ring-blue-200" :
    tone === "success" ? "ring-emerald-200" :
    tone === "warning" ? "ring-amber-200" :
    "ring-slate-200";
  return (
    <div className={`bg-white rounded-xl p-4 ring-1 ${ringClass} shadow-sm`}>
      <div className="text-xs text-slate-500 uppercase tracking-wider">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}
