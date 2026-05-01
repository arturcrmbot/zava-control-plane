# POC2 — Quick Demo Script

End-to-end walkthrough you can record in ~5 minutes. Covers candidate apply → triage → recruiter view → screening call → offer decision, with the right places to look at logs along the way.

> Full 30-min runbook lives in [poc2-DEMO.md](poc2-DEMO.md). This file is the **short version** — what to click, in what order, to prove the stack works.

---

## 0 · Pre-flight (30 seconds)

All five services must respond. From any shell:

```bash
curl -s -o /dev/null -w "azurite:%{http_code}\n" http://localhost:10000/devstoreaccount1
curl -s -o /dev/null -w "fastapi:%{http_code}\n" http://localhost:3001/api/portal/admin/candidates
curl -s -o /dev/null -w "func:%{http_code}\n"    http://localhost:7071/
curl -s -o /dev/null -w "admin:%{http_code}\n"   http://localhost:5173/
curl -s -o /dev/null -w "portal:%{http_code}\n"  http://localhost:5174/
```

Expected: `400 / 200 / 200 / 200 / 200`. If anything is missing, see the [logs section](#logs) at the bottom.

Open three browser tabs, side-by-side:

| Tab | URL | What it is |
|-----|-----|-----------|
| **Portal**    | http://localhost:5174           | Public candidate-facing app |
| **Recruiter** | http://localhost:5174/recruiter | List of candidates + per-candidate decisions |
| **Admin**     | http://localhost:5173           | Domain-neutral Control Plane |

---

## 1 · Apply (the candidate side) · 30 sec

1. On the **Portal** tab, you land on the apply form.
2. Pick role **Senior Data Engineer · USA** (`REQ-SDE-USA-DEMO`).
3. Fill name + email — anything works; suggested:
   - Name: `John Sample`
   - Email: `john.sample@example.com`
4. Drop in a CV PDF. Easiest: `data/synthetic/hiring/cv-pdfs/C-SE-USA-00.pdf` (any of the synthetic ones works; they're real PDFs the agent will OCR).
5. Submit. You'll see `submitted, candidate_id=C-XXXXXXXX`. **Copy that ID** — you'll use it.

> What just happened: `/api/portal/apply` wrote the bytes to Azurite blob + staged a copy under `data/synthetic/hiring/cv-pdfs/<candidate_id>.pdf`, attached the candidate to seeded workflow `HIRE-DEMO-01`, and emitted `candidate.applied`. The portal subscriber then issued a status-link email and started a `HiringOrchestrator` Durable instance that auto-approves Phase 1 (Budget) and runs through to Triage.

---

## 2 · Watch Triage run · 30–90 sec

On the **Recruiter** tab, click into your new candidate.

You should see **phase: Review (Triage)** for ~10–60 seconds, then move to **Screening** or **Awaiting screening call** depending on the verdict.

While it's running, the panel **"How the agent reasoned · cv_crystalliser"** populates with the **real LLM trace**:

- A clickable `tool · ocr_extract` row showing the args (the candidate ID + `prebuilt-layout` model) and the trimmed Document Intelligence response.
- `final LLM response` — the structured profile the model returned, plus token usage.
- A latency chip (e.g. `12.3s · 1 tool call(s)`) in the panel header.

> If you only see "awaiting LLM run" for more than a minute, check `logs/func.log` for the agent run — see [logs](#logs).

---

## 3 · The voice screening call · 90 sec

If the candidate's verdict is borderline / strong, the orchestrator suspends at Phase 6 (Voice) and emails a single-use screening link.

1. On the **Recruiter** candidate page, look at **Active magic links** at the bottom. Find the row with scope `screen`.
2. Copy the token.
3. Open `http://localhost:5174/screen?token=<paste-here>` in a new tab.
4. Click the green **Start call** button. Allow mic. Have a 30-second chat.
5. Click **End call**. You're redirected back to the portal.

Back on the **Recruiter** tab, refresh — the candidate should now show **Voice screening transcript** with the conversation turns, and the workflow should advance past Voice.

> Mic not available? Set `VITE_VOICE_TRANSPORT=canned` and rebuild the portal — the screen page exposes a single "Submit canned transcript" button instead.

---

## 4 · The recruiter view (the money shot) · 60 sec

Still on the **Recruiter** candidate page. This is the page to linger on:

- **Header** — name, role, jurisdiction, current phase, **Download CV** link.
- **What we learned** — the canonical profile (current role, total tenure, right to work, top skills, recent work history).
- **How the agent reasoned** — every `ocr_extract` call expanded shows the args + trimmed result; the final LLM response is collapsible.
- **Verdict** — green/amber/red callout with the model's confidence + rationale.
- **Voice screening transcript** — turn-by-turn replay of the conversation.
- **Audit timeline** — every orchestration step with timestamps and actor (`agent:orchestrator`, `human:operator`, etc.).
- **Active magic links** — copy/paste fallback when ACS Email is offline.

This is the "who is this person, what did we learn, what did the AI decide" view we built today.

---

## 5 · The admin / Control-Plane view · 30 sec

On the **Admin** tab (`:5173`):

1. Find your hiring workflow in the list. Click in.
2. The header shows **type: hiring** with a **"Open recruiter view"** deep-link → jumps back to the recruiter page for this workflow.
3. If it's parked at Voice/Offer, you should see:
   > **Awaiting external party** _(no domain copy, no red-alert dashboard)_

4. **Compare** by opening any expense workflow — the wait label says *"Awaiting operator review"* and the deep-link reads *"Open reviewer queue"*. **Zero hiring vocabulary** appears on the expense page. That's the platform-vs-domain split working.

---

## 6 · Offer accept / decline · 30 sec

Once the workflow reaches Phase 9 (Offer) it suspends and an offer-scope magic link is issued.

1. **Recruiter** page → **Active magic links** → copy the `offer` token.
2. POST the decision:
   ```bash
   curl -X POST "http://localhost:3001/api/portal/offer/<token>?decision=accept"
   ```
3. Refresh the recruiter page — the workflow advances to **Onboarding**, the action ledger gains `workflow.completed`, the offer token disappears from the active list.

(For the recorded demo, `decline` also works — it short-circuits to status=rejected.)

---

## 7 · Where to look if something goes sideways

<a id="logs"></a>

| Symptom | Where to look |
|---------|---------------|
| Apply returns 503 "blob storage unavailable" | Azurite isn't running. `tail logs/azurite.log` |
| Apply returns 404 "no workflow for role_id" | FastAPI didn't seed reqs. `tail logs/fastapi.log` for `seed_demo_reqs` line |
| Triage panel stuck at "awaiting LLM run" | `tail -f logs/func.log` — look for `agent.completed` or a `gh auth token` failure |
| Recruiter view 404 / loading forever | `curl http://localhost:3001/api/portal/admin/candidate/C-XXXXXXXX` — the FastAPI side |
| Admin view shows hiring strings on an expense workflow | Vite didn't HMR. Hard-refresh `:5173` (Ctrl-Shift-R) |

To restart just the Python services (keep Azurite + Vite warm):

```bash
# kill PIDs from `netstat -ano | findstr LISTENING | findstr ":3001 :7071"`
# then:
uv run uvicorn api.server.main:app --port 3001 > logs/fastapi.log 2>&1 &
cmd //c "scripts\\run-func.bat" > logs/func.log 2>&1 &
```

---

## TL;DR — record this in one take

```
Portal :5174       → apply (any synthetic PDF)            → ~5s
Recruiter :5174/r  → click candidate, narrate LLM trace   → ~30s
Recruiter         → copy screen token, do voice call     → ~60s
Recruiter         → narrate transcript + verdict + audit → ~30s
Admin :5173        → open same workflow, point at        → ~30s
                     "Awaiting external party" + deep-link
Admin             → open an expense workflow, prove no   → ~15s
                     hiring strings appear
Recruiter         → copy offer token, accept via curl    → ~15s
Recruiter         → workflow → Onboarding, done          → ~5s
```

Total: under 4 minutes if you don't pause to talk.
