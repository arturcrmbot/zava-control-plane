import { useState } from "react";

type Props = {
  token: string;
  url: string | null;
  onDecided: () => void;
};

export default function OfferPanel({ token, url, onDecided }: Props) {
  const [submitting, setSubmitting] = useState<"accept" | "decline" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function decide(decision: "accept" | "decline") {
    setSubmitting(decision);
    setError(null);
    try {
      const resp = await fetch(
        `/api/portal/offer/${encodeURIComponent(token)}?decision=${decision}`,
        { method: "POST" },
      );
      if (!resp.ok) {
        setError(`Decision failed (${resp.status})`);
        return;
      }
      onDecided();
    } catch (err) {
      setError(`Network error: ${(err as Error).message}`);
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <div className="panel">
      <div className="panel-header">Your offer</div>
      <div className="panel-body space-y-4">
        {url && (
          <a href={url} target="_blank" rel="noreferrer" className="btn-secondary">
            View offer letter (PDF)
          </a>
        )}
        <div className="flex gap-2">
          <button
            type="button"
            className="btn-primary"
            onClick={() => decide("accept")}
            disabled={submitting !== null}
          >
            {submitting === "accept" ? "Accepting…" : "Accept"}
          </button>
          <button
            type="button"
            className="btn-danger"
            onClick={() => decide("decline")}
            disabled={submitting !== null}
          >
            {submitting === "decline" ? "Declining…" : "Decline"}
          </button>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
    </div>
  );
}
