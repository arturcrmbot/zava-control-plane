export interface FlaggedExperiment {
  id: string;
  control_score: number;
  treatment_score: number;
  delta: number;
  n_samples: number;
}

export interface FlaggedItem {
  lesson_id: string;
  body: string;
  proposed_by: string;
  flag_reason: string;
  delta: number;
  n_samples: number;
  proposed_at: string | null;
  experiment: FlaggedExperiment | null;
}

export async function listFlagged(domain: string): Promise<FlaggedItem[]> {
  const resp = await fetch(`/api/dream-pass/flagged?domain=${encodeURIComponent(domain)}`);
  if (!resp.ok) throw new Error(`list flagged failed: ${resp.status}`);
  const body = await resp.json();
  return body.items as FlaggedItem[];
}

export async function approveFlagged(lessonId: string, approver: string): Promise<void> {
  const resp = await fetch(`/api/dream-pass/flagged/${encodeURIComponent(lessonId)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approver }),
  });
  if (!resp.ok) throw new Error(`approve failed: ${resp.status}`);
}

export async function rejectFlagged(
  lessonId: string,
  reviewer: string,
  reason: string,
): Promise<void> {
  const resp = await fetch(`/api/dream-pass/flagged/${encodeURIComponent(lessonId)}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer, reason }),
  });
  if (!resp.ok) throw new Error(`reject failed: ${resp.status}`);
}
