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

export async function getScreenResolve(
  token: string,
): Promise<{ candidate_id: string }> {
  const resp = await fetch(
    `/api/portal/voice/screen-resolve?token=${encodeURIComponent(token)}`,
  );
  if (resp.status === 410) throw new Error("expired");
  if (!resp.ok) throw new Error(`screen-resolve failed (${resp.status})`);
  return (await resp.json()) as { candidate_id: string };
}

export async function postTranscript(
  candidateId: string,
  body: { token: string; transcript: unknown; score: number; duration_s: number },
): Promise<void> {
  const resp = await fetch(
    `/api/portal/voice/${encodeURIComponent(candidateId)}/transcript`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!resp.ok) throw new Error(`transcript failed (${resp.status})`);
}

export async function postCannedScreen(candidateId: string, token: string): Promise<void> {
  const resp = await fetch(
    `/api/portal/voice/${encodeURIComponent(candidateId)}/canned?token=${encodeURIComponent(token)}`,
    { method: "POST" },
  );
  if (!resp.ok) throw new Error(`canned screen failed (${resp.status})`);
}

export type AdminLink = {
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

export async function getAdminLinks(): Promise<AdminLink[]> {
  const resp = await fetch("/api/portal/admin/links");
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const body = (await resp.json()) as { links?: AdminLink[] };
  return Array.isArray(body.links) ? body.links : [];
}
