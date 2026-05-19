import { useEffect, useState } from "react";
import {
  FlaggedItem,
  approveFlagged,
  listFlagged,
  rejectFlagged,
} from "../api/dreamPassExceptions";

const DOMAINS = ["hiring", "vendor_kyc", "expense_claim"];

export default function DreamPassExceptions() {
  const [domain, setDomain] = useState("hiring");
  const [items, setItems] = useState<FlaggedItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    setError(null);
    try {
      setItems(await listFlagged(domain));
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domain]);

  async function onApprove(item: FlaggedItem) {
    const approver = prompt("operator email")?.trim();
    if (!approver) return;
    setBusy(true);
    try {
      await approveFlagged(item.lesson_id, approver);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onReject(item: FlaggedItem) {
    const reviewer = prompt("operator email")?.trim();
    if (!reviewer) return;
    const reason = prompt("reject reason")?.trim();
    if (!reason) return;
    setBusy(true);
    try {
      await rejectFlagged(item.lesson_id, reviewer, reason);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ padding: 16, fontFamily: "system-ui, sans-serif" }}>
      <h1>Dream-pass exceptions</h1>
      <p>
        Candidate lessons the dream-pass policy refused to auto-promote.
        Approve to make active, reject to prune.
      </p>
      <label>
        Domain:&nbsp;
        <select value={domain} onChange={(e) => setDomain(e.target.value)} disabled={busy}>
          {DOMAINS.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      </label>

      {error && <div style={{ color: "red", marginTop: 12 }}>{error}</div>}

      <table style={{ width: "100%", marginTop: 16, borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th align="left">Lesson</th>
            <th align="left">Flag reason</th>
            <th align="right">Δ</th>
            <th align="right">n</th>
            <th align="left">Proposed by</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.lesson_id} style={{ borderTop: "1px solid #ddd" }}>
              <td style={{ padding: "8px 0" }}>{item.body}</td>
              <td>{item.flag_reason}</td>
              <td align="right">{item.delta.toFixed(3)}</td>
              <td align="right">{item.n_samples}</td>
              <td>{item.proposed_by}</td>
              <td>
                <button onClick={() => onApprove(item)} disabled={busy}>Approve</button>
                <button onClick={() => onReject(item)} disabled={busy} style={{ marginLeft: 4 }}>
                  Reject
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {items.length === 0 && !error && (
        <p style={{ marginTop: 16, color: "#666" }}>No flagged candidates for {domain}.</p>
      )}
    </div>
  );
}
