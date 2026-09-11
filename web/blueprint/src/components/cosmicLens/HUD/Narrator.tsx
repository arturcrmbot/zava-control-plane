import { useEffect, useState } from "react";
import {
  readJourneyDetails,
  resolveJourneyDecision,
  type GuidedJourney,
  type JourneyDetails,
} from "./guidedJourney";

const STATUS_LABELS: Record<string, string> = {
  pending: "Not reached",
  in_progress: "Running",
  awaiting_hitl: "Awaiting operator",
  completed: "Completed",
  failed: "Failed",
  rejected: "Rejected",
};

interface NarratorProps {
  journey: GuidedJourney;
  onClose: () => void;
  onInspect?: (workflowId: string) => void;
}

/** Observed workflow evidence, not a timed script of assumed business outcomes. */
export function Narrator({ journey, onClose, onInspect }: NarratorProps) {
  const [detail, setDetail] = useState<JourneyDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [deciding, setDeciding] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function refresh() {
      let terminal = false;
      try {
        const next = await readJourneyDetails(journey.workflowId);
        if (cancelled) return;
        setDetail(next);
        setLoadError(null);
        terminal = next?.status === "completed" || next?.status === "failed";
      } catch (error) {
        if (cancelled) return;
        setLoadError(error instanceof Error ? error.message : "Could not load workflow evidence");
      } finally {
        if (!cancelled) setLoading(false);
      }
      if (!cancelled && !terminal) {
        timer = setTimeout(refresh, 1000);
      }
    }
    void refresh();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [journey.workflowId, journey.source, refreshVersion]);

  async function decide(resolution: "approve" | "reject") {
    if (!detail?.activeExceptionId || journey.source !== "live") {
      setActionError("No live operator decision is pending.");
      return;
    }
    setDeciding(true);
    setActionError(null);
    try {
      await resolveJourneyDecision(detail.activeExceptionId, resolution);
      setRefreshVersion((value) => value + 1);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not submit the decision");
    } finally {
      setDeciding(false);
    }
  }

  const visibleError = actionError || loadError;
  const canDecide = journey.source === "live" &&
    detail?.workflowType === "aurora-budget-response" &&
    detail.status === "awaiting_hitl" && !!detail.activeExceptionId;
  const evidenceUrl = `/api/workflows/${encodeURIComponent(journey.workflowId)}`;
  const outcome = detail?.outcome || detail?.status || "";

  return (
    <section className="journey-evidence" aria-label="Guided workflow evidence">
      <header className="journey-evidence__header">
        <div>
          <span className="journey-evidence__source" data-testid="journey-source-mode">
            {journey.source === "replay" ? "Recorded execution" : "Live workflow"}
          </span>
          <h2>{detail?.workflowType === "aurora-budget-response" ? "Aurora budget response" : "Workflow evidence"}</h2>
        </div>
        <button type="button" className="journey-button" onClick={onClose} aria-label="Close guided journey">
          Close
        </button>
      </header>
      <code className="journey-evidence__id" data-testid="journey-root-id">{journey.workflowId}</code>

      {visibleError && (
        <div className="journey-evidence__error" role="alert">
          {visibleError}
          {loadError && (
            <button className="journey-button" onClick={() => setRefreshVersion((value) => value + 1)}>
              Retry evidence
            </button>
          )}
        </div>
      )}

      {loading && <p>Loading execution evidence...</p>}
      {!loading && !detail && (
        <p>No workflow evidence is available yet. No outcome is being assumed.</p>
      )}
      {detail && (
        <>
          <p data-testid="journey-status" data-status={detail.status} aria-live="polite">
            {STATUS_LABELS[outcome] || outcome.replace(/_/g, " ")}
          </p>
          {detail.reason && <p>{detail.reason}</p>}
          {detail.phases.length === 0 && <p>No phase checkpoint has been recorded yet.</p>}
          <ol className="journey-evidence__phases">
            {detail.phases.map((phase) => (
              <li key={phase.name} data-status={phase.status}>
                <span>{phase.name}</span>
                <span>{
                  outcome === "rejected" && phase.name === detail.currentPhase
                    ? "Rejected"
                    : STATUS_LABELS[phase.status] || phase.status
                }</span>
              </li>
            ))}
          </ol>
          {detail.recommendation && <p className="journey-evidence__recommendation">{detail.recommendation}</p>}
          {detail.policyDecisionId && <p>Policy decision: <code>{detail.policyDecisionId}</code></p>}
          {detail.children.length > 0 && (
            <div className="journey-evidence__children">
              <h3>Invoice workflows</h3>
              {detail.children.map((child) => (
                <div key={child.workflowId}>
                  {onInspect
                    ? <button className="journey-link" onClick={() => onInspect(child.workflowId)}>{child.workflowId}</button>
                    : <code>{child.workflowId}</code>}
                  <span>{child.status ? STATUS_LABELS[child.status] || child.status : "Outcome not recorded"}</span>
                </div>
              ))}
            </div>
          )}
          {canDecide && (
            <div className="journey-evidence__decision">
              <p>CFO decision required. Review the evidence before acting.</p>
              <button className="journey-button journey-button--primary" disabled={deciding || !!loadError} onClick={() => void decide("approve")}>
                Approve recommendation
              </button>
              <button className="journey-button" disabled={deciding || !!loadError} onClick={() => void decide("reject")}>
                Reject recommendation
              </button>
            </div>
          )}
        </>
      )}
      <footer className="journey-evidence__footer">
        {onInspect && <button className="journey-button" onClick={() => onInspect(journey.workflowId)}>Inspect workflow</button>}
        <a data-testid="journey-evidence-link" href={evidenceUrl} target="_blank" rel="noopener noreferrer">Raw evidence</a>
      </footer>
    </section>
  );
}
