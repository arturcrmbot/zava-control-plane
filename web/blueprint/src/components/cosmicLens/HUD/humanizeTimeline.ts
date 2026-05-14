/**
 * Timeline-specific consumer of `@shared/humanize`.
 *
 * Adds three timeline concerns on top of the shared label dictionary:
 *   • drop noisy duplicate rows (tool spans, passing schema validators,
 *     phase.completed action_ledger entries)
 *   • compute a workflow-relative time offset
 *   • assign a tone (ok / warn / bad / milestone) for the row dot
 *
 * Wording for individual labels lives in `web/shared/humanize.ts`. Do not
 * fork the dictionary here — add an entry to `EXECUTOR_OVERRIDES` instead.
 */

import {
  humanizeLabel,
  isValidatorLabel,
  validatorTarget,
  prettyActor,
  formatOffset,
  verdictVerb,
  titleCase,
} from "../../../../../shared/humanize";

export interface RawTimelineEvent {
  ts?: number;
  kind: string;
  label?: string;
  status?: string;
  actor?: string;
  verdict?: string;
  reason?: string;
  result_summary?: string | null;
  tokens?: number | null;
  details?: Record<string, unknown> | null;
  completed_at?: number | null;
}

export interface HumanEvent {
  ts: number;
  /** seconds since the first event in the workflow */
  offsetSec: number;
  /** "+12s", "+1m 4s", "+2h 15m" */
  when: string;
  what: string;
  who: string;
  /** soft note shown beneath `what` (e.g. decision reason) */
  detail?: string;
  /** ok | warn | bad | milestone | muted — drives the dot colour */
  tone: "ok" | "warn" | "bad" | "milestone" | "muted";
}

export function humanizeTimeline(rows: RawTimelineEvent[]): HumanEvent[] {
  if (!rows.length) return [];

  const filtered = rows.filter((r) => {
    if (r.kind === "tool") return false;
    const label = r.label ?? "";
    if (label.startsWith("phase.completed:")) return false;
    if (isValidatorLabel(label) && (r.status ?? "ok") === "ok") return false;
    return true;
  });

  if (!filtered.length) return [];
  const t0 = filtered[0].ts ?? 0;
  return filtered
    .map((r) => toHuman(r, t0))
    .filter((h): h is HumanEvent => h !== null);
}

function toHuman(r: RawTimelineEvent, t0: number): HumanEvent | null {
  const ts = r.ts ?? t0;
  const offsetSec = Math.max(0, ts - t0);
  const when = formatOffset(offsetSec);

  if (r.kind === "decision") {
    const actor = prettyActor(r.actor ?? "Reviewer");
    const phaseLabel = r.label ?? "the step";
    // The label may be a phase id like "brief_capture"; render it titled.
    const phase = phaseLabel.includes("_") ? titleCase(phaseLabel) : phaseLabel;
    const verdict = r.verdict ?? "decided";
    return {
      ts, offsetSec, when,
      what: `${actor} ${verdictVerb(verdict)} ${phase}`,
      who: actor,
      detail: r.reason ?? undefined,
      tone: verdict === "approve" ? "ok" : verdict === "reject" ? "bad" : "warn",
    };
  }

  if (r.kind === "phase") {
    const phaseLabel = r.label ?? "phase";
    const phase = phaseLabel.includes("_") ? titleCase(phaseLabel) : phaseLabel;
    const status = r.status ?? "";
    return {
      ts, offsetSec, when,
      what: status === "completed" ? `${phase} complete` : `Started: ${phase}`,
      who: "Workflow",
      tone: "milestone",
    };
  }

  const label = r.label ?? "";
  const failed = (r.status ?? "ok") !== "ok";

  if (isValidatorLabel(label)) {
    return {
      ts, offsetSec, when,
      what: `Output check failed: ${validatorTarget(label)}`,
      who: "AI agent",
      detail: r.result_summary ?? undefined,
      tone: "bad",
    };
  }

  const { text, who } = humanizeLabel(label);
  let tone: HumanEvent["tone"] = failed ? "bad" : "ok";
  if (label === "workflow.started") tone = "milestone";
  else if (label === "suspended") tone = "warn";

  return {
    ts, offsetSec, when,
    what: text,
    who,
    detail: r.result_summary ?? undefined,
    tone,
  };
}
