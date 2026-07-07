export async function createSession(input: { text?: string; file?: File }): Promise<string> {
  const body = new FormData();
  if (input.file) body.append("file", input.file);
  if (input.text) body.append("text", input.text);
  const r = await fetch("/api/compose/session", { method: "POST", body });
  if (!r.ok) throw new Error(`create failed: ${r.status}`);
  return (await r.json()).compose_id as string;
}

export async function postAnswer(cid: string, request_id: string, answer: string) {
  await fetch(`/api/compose/${cid}/answer`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ request_id, answer }),
  });
}

export async function postBrief(cid: string, request_id: string, approved: boolean, yaml: string) {
  await fetch(`/api/compose/${cid}/brief`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ request_id, approved, yaml }),
  });
}

export async function postIgnite(cid: string) {
  await fetch(`/api/compose/${cid}/ignite`, { method: "POST" });
}

export async function pollComposition(workflowType: string, timeoutMs = 120000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const r = await fetch("/api/blueprint/composition");
      if (r.ok) {
        const d = await r.json();
        if ((d.domains ?? []).some((x: any) => x.workflow_type === workflowType)) return true;
      }
    } catch { /* server restarting; keep polling */ }
    await new Promise((res) => setTimeout(res, 2000));
  }
  return false;
}
