# Demo: EMS Extensibility (AC #10)

> **What this demonstrates:** A third Expense Management System lands on the
> platform with **no skill, agent, or workflow changes**. Only the lookup
> adapter and the EMS mock are touched. The architectural property is that
> skills are EMS-agnostic — the adapter normalises every EMS into the same
> claim shape, and every downstream agent (classifier, receipt validator,
> notifier, arbitrator, audit summariser) is unchanged.

**Time:** 2 minutes during the live demo. Read aloud while showing the diff
side-by-side.

---

## The pitch (15 sec, before the diff)

> "POC1 ships with two EMSs wired — Workday and Concur. The acceptance
> criterion says we should be able to add a third without touching the
> agent or the skills. We're going to add Maconomy live, in two files."

## The diff (90 sec, on screen)

Show this `git diff` in the terminal next to a browser tab pointing at
`http://localhost:4103/mcp/tools` (the running Maconomy mock).

### File 1 — `mocks/maconomy-mcp/server.ts`

The mock. One Express endpoint, `getExpenseLine`, that returns a single
synthetic claim under the canonical shape (the same shape the synthetic
corpus uses). 60 lines including imports.

```typescript
app.post("/mcp/call/:tool", (req, res) => {
  const tool = req.params.tool;
  const args = (req.body ?? {}) as Record<string, unknown>;
  switch (tool) {
    case "getExpenseLine": {
      const id = args["claimId"];
      const c = data.claims.find(x => x.claim_id === id);
      return c ? res.json(c) : res.status(404).json({ error: "claim_not_found" });
    }
    // ...
  }
});
```

### File 2 — `api/server/mcp_tools/claim_lookup.py`

The dispatcher. Eight new lines: a `maconomy` branch that calls the new
endpoint and returns the record verbatim (it's already in canonical shape).

```python
if ems == "maconomy":
    port = int(os.environ.get("MACONOMY_MCP_PORT", "4103"))
    url = f"http://127.0.0.1:{port}/mcp/call/getExpenseLine"
    resp = httpx.post(url, json={"claimId": claim_id}, timeout=5.0)
    if resp.status_code == 404:
        raise KeyError(f"claim {claim_id!r} not found at maconomy mock")
    resp.raise_for_status()
    return resp.json()
```

`_resolve_ems` also adds `"maconomy"` to its valid-EMS set.

## What was *not* touched (15 sec, key talking point)

Drop these into the terminal one after another so the audience sees the
absence of churn:

```bash
git diff --name-only HEAD~1 -- api/server/skills/
# → empty. No skill changes.

git diff --name-only HEAD~1 -- api/functions/graphs/
# → empty. No agent or graph changes.

git diff --name-only HEAD~1 -- api/functions/workflows/
# → empty. No orchestrator changes.
```

> "Two files. The skill manifests, the agents, the validators, the
> orchestrator — all unchanged. The platform absorbs the new EMS because
> the only thing that's EMS-specific is the dispatcher."

## End-to-end (30 sec, optional if time allows)

Spawn a Maconomy claim and watch it run through all 7 phases identically
to a Workday claim:

```bash
curl -X POST http://localhost:8000/api/simulator/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario": "maconomy-baseline"}'
```

Open the dashboard: the new workflow appears with no EMS marker on the
card; the audit drawer shows `ems_source: "maconomy"` and the same
classification → notification → audit ledger as Workday or Concur.

---

## Architectural property (recap, 15 sec close)

```
EMS-specific code  ──►  api/server/mcp_tools/claim_lookup.py  (dispatcher)
                       mocks/<ems>-mcp/server.ts             (per-EMS adapter)

EMS-agnostic code  ──►  api/server/skills/*                   (untouched)
                       api/functions/graphs/executors/agents/* (untouched)
                       api/functions/graphs/*                 (untouched)
                       api/functions/workflows/*              (untouched)
```

This is the AC #10 property: ratio of "code that changes per new EMS" to
"code that doesn't" stays at roughly 1:50. New EMSs don't bend the rest of
the system.
