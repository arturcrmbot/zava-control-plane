import { useState } from "react";
import { postOfferDecision } from "../lib/api";

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
      await postOfferDecision(token, decision);
      onDecided();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <div className="panel-elevated">
      <div className="panel-header">
        <span><span className="status-dot status-dot-active"/> Your offer is ready</span>
        <span className="chip-warning">single-use link · respond once</span>
      </div>
      <div className="panel-body space-y-5">
        <p className="text-sm text-slate-700">
          Congratulations — the hiring panel has decided to move forward with
          you. Review the offer letter and respond below. Your decision is
          final.
        </p>

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 flex items-center justify-between">
          <div className="text-sm">
            <div className="font-medium text-slate-800">Offer letter (PDF)</div>
            <div className="text-xs text-slate-500">
              {url ? "Click to open in a new tab" : "Offer letter is being generated…"}
            </div>
          </div>
          {url ? (
            <a href={url} target="_blank" rel="noreferrer" className="btn-secondary">
              View letter ↗
            </a>
          ) : (
            <span className="spinner"/>
          )}
        </div>

        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <button
            type="button"
            className="btn-success btn-large flex-1"
            onClick={() => decide("accept")}
            disabled={submitting !== null}
          >
            {submitting === "accept" ? <><span className="spinner"/> Accepting…</> : "✓ Accept offer"}
          </button>
          <button
            type="button"
            className="btn-danger flex-1"
            onClick={() => decide("decline")}
            disabled={submitting !== null}
          >
            {submitting === "decline" ? <><span className="spinner"/> Declining…</> : "Decline politely"}
          </button>
        </div>

        {error && (
          <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
