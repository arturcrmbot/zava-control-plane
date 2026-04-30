// Typed fetch helpers for the candidate portal. Routes are all under /api/portal/*.

export type ApplyResponse = {
  status: "submitted";
  candidate_id: string;
  workflow_id?: string;
};

export async function postApply(form: FormData): Promise<ApplyResponse> {
  const resp = await fetch("/api/portal/apply", { method: "POST", body: form });
  if (resp.status !== 202) {
    throw new Error(`apply failed (${resp.status})`);
  }
  return (await resp.json()) as ApplyResponse;
}

export async function getStatus<T>(token: string): Promise<T> {
  const resp = await fetch(`/api/portal/status/${encodeURIComponent(token)}`);
  if (!resp.ok) throw new Error(`status failed (${resp.status})`);
  return (await resp.json()) as T;
}

export async function postOfferDecision(
  token: string,
  decision: "accept" | "decline",
): Promise<{ ok: boolean; decision: string }> {
  const resp = await fetch(
    `/api/portal/offer/${encodeURIComponent(token)}?decision=${decision}`,
    { method: "POST" },
  );
  if (!resp.ok) throw new Error(`decision failed (${resp.status})`);
  return (await resp.json()) as { ok: boolean; decision: string };
}
