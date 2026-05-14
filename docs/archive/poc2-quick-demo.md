# POC2 — Quick Demo Script

End-to-end walkthrough of the **recruiter HITL hiring flow**. Apply → triage → screening call → recruiter invite → candidate books → recruiter post-interview decision → candidate accepts offer. ~5–8 minutes once you know it.

This file is the **short version** — what to click, in what order, to prove the stack works.

The hiring orchestrator runs 10 phases. **Phase 7 (Interview)** is the new bit — three sequential HITL waits:

```
… Voice (candidate HITL)
  → Phase 7 ① awaiting_interview_invite     (operator_review)  ← recruiter
  → Phase 7 ② awaiting_interview_booking    (external_party)   ← candidate picks slot
  → Phase 7 ③ awaiting_interview_complete   (operator_review)  ← recruiter
  → Compliance → Offer (candidate accept/decline) → Onboarding
```

Recruiter view at `:5274/recruiter` paints a different action panel for each `awaiting_reason`.

---

## 0 · Pre-flight (30 seconds)

All five services must respond:

```bash
curl -s -o /dev/null -w "azurite:%{http_code}\n" http://localhost:10000/devstoreaccount1
curl -s -o /dev/null -w "fastapi:%{http_code}\n" http://localhost:3101/api/portal/admin/candidates
curl -s -o /dev/null -w "func:%{http_code}\n"    http://localhost:7071/
curl -s -o /dev/null -w "admin:%{http_code}\n"   http://localhost:5273/
curl -s -o /dev/null -w "portal:%{http_code}\n"  http://localhost:5274/
```

Expected: `400 / 200 / 200 / 200 / 200`. If anything is missing, see [logs](#logs).

Open three browser tabs:

| Tab | URL | What it is |
|-----|-----|-----------|
| **Portal**    | http://localhost:5274           | Public candidate-facing app |
| **Recruiter** | http://localhost:5274/recruiter | Candidate list + per-candidate decision panels |
| **Admin**     | http://localhost:5273           | Domain-neutral Control Plane (workflow detail) |

---

## 1 · Apply as the candidate · 30 sec

1. On the **Portal** tab, you land on the apply form.
2. Pick **Senior Data Engineer · USA** (`REQ-SDE-USA-DEMO`).
3. Fill name + email — anything works. Suggested: `John Sample` / `john.sample@example.com`.
4. Drop in a CV PDF — easiest: `data/synthetic/hiring/cv-pdfs/C-SE-USA-00.pdf` (any of the synthetic ones works; they're real PDFs the agent will OCR).
5. Submit. The response shows `submitted, candidate_id=C-XXXXXXXX`. **Copy that ID** — you'll use it.

> What just happened: the bytes were written to Azurite blob, a copy was staged at `data/synthetic/hiring/cv-pdfs/<candidate_id>.pdf`, the candidate was attached to seeded workflow `HIRE-DEMO-01`, a `candidate.applied` event fired, the portal subscriber issued a status-link email and started a `HiringOrchestrator` Durable instance that auto-approves Phase 1 (Budget) and runs through to Triage.

---

## 2 · Watch the AI do triage · 30–90 sec

On the **Recruiter** tab, click into your candidate. Phase will be `Review (Triage)` for ~10–60 seconds.

Panel **"What we learned · cv_crystalliser"** populates with a real LLM trace:
- A clickable `tool · ocr_extract` row showing args + the trimmed Document Intelligence response.
- Final LLM response — the structured profile the model returned, plus token usage.
- A latency chip in the panel header, e.g. `12.3s · 1 tool call(s)`.

If `extraction_status === "failed"` you'll see a red chip and a "no verdict" panel — no fabricated shortlist.

---

## 3 · Voice screening call · 60–90 sec

Once Triage clears, the workflow suspends at `awaiting_voice_complete`. The candidate gets emailed a screen-scope token.

**Real call (mic + speakers required):**
1. Recruiter view → **Active magic links** → copy the `screen` token.
2. Open `http://localhost:5274/screen?token=<token>` in a new tab.
3. Click **Start screening call**, allow mic. Have ~30 seconds of conversation.
4. Click **End call**. Page flips to "Thanks — call ended" with a "View my application status" button.

**Fast path (no mic / scripted demo):** post a fake transcript directly:
```bash
SCREEN_TOK=$(curl -s "http://localhost:3101/api/portal/admin/candidate/<CID>" \
  | python -c "import sys,json; print([t['token'] for t in json.load(sys.stdin)['active_tokens'] if t['scope']=='screen'][0])")
curl -s -X POST "http://localhost:3101/api/portal/voice/<CID>/transcript" \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$SCREEN_TOK\",\"transcript\":[{\"role\":\"agent\",\"text\":\"hi\",\"ts\":0}],\"score\":7.5,\"duration_s\":60}"
```

Either way, the recruiter view picks up the transcript turns under "Voice screening transcript".

---

## 4 · Gate ① · Recruiter "invite to interview?" · 60 sec  ⭐ NEW

After the call completes, the workflow suspends at `awaiting_interview_invite` (`wait_kind: operator_review`). Behind the scenes the `interview-recommender` agent has already run with the CV + screening verdict + voice transcript as context.

On the **Recruiter** candidate page (refresh if needed — auto-polls every 8s), a new panel appears:

> **Decision · invite to interview?** — *awaiting recruiter*
>
> AI rec card: "AI recommends: advance · Strong on Spark, vague on stakeholder management — would push on EM experience in interview" plus 2-4 talking points.
>
> Optional reason textarea. **Invite to interview** / **Reject** buttons.

Click **Invite to interview**.

> What happens: `interview_invite` Durable event raises with `decision=invite`. Orchestrator advances to gate ②.

(Try the reject path with another candidate later — see [Reject paths](#reject-paths).)

---

## 5 · Gate ② · Candidate picks an interview slot · 60 sec  ⭐ NEW

Workflow suspends at `awaiting_interview_booking` (`wait_kind: external_party`). The candidate gets emailed a `book_interview`-scope link, single-use, 7-day TTL.

On the **Recruiter** candidate page, the panel switches to:

> **Awaiting candidate to book interview**
>
> "The candidate has been emailed an interview-booking link." Plus the operator copy/paste fallback URL.

Open that URL (or grab the token from active magic links and visit `/book?token=<token>`):

- 5 weekdays × 3 slots/day = 15 slot buttons grouped by day, ~80% available.
- Pick any available slot. Page flips to **"Interview booked"** with the chosen time.

> What happens: token consumed, slot persisted on the candidate dict, `interview_booked` event raises with the slot. Orchestrator runs the recommender again (gate ③ context) and advances.

---

## 6 · Gate ③ · Recruiter post-interview decision · 90 sec  ⭐ NEW

Workflow suspends at `awaiting_interview_complete` (`wait_kind: operator_review`). The recommender just ran a second time.

(Skip the "actual interview" — pretend it happened in Teams.)

On the **Recruiter** candidate page, new panel:

> **Post-interview decision** — *awaiting recruiter*
>
> AI rec card: "AI recommends: advance · suggested level: Senior · …rationale…"
>
> - **Interview notes** textarea.
> - **Overall rating**: 1-5 buttons.
> - **Decision**: Offer / Reject dropdown.
> - **Level**: dropdown sourced per-role-family. For SDE: Mid-Level / Senior / Staff / Principal.
> - **Submit decision** button.

Fill: rating=4, decision=Offer, level=Senior, notes=`"Strong on Spark, communicates clearly."`. Submit.

> What happens: `offer_decision` event raises with `{decision: "offer", level, notes, rating}`. Orchestrator advances Phase 7 → Compliance → Phase 9 (Offer letter, candidate accept/decline).

---

## 7 · Candidate accepts the offer · 30 sec

Workflow suspends at `awaiting_offer_approval` (`wait_kind: external_party`). The candidate gets an `offer`-scope token.

```bash
OFFER_TOK=$(curl -s "http://localhost:3101/api/portal/admin/candidate/<CID>" \
  | python -c "import sys,json; print([t['token'] for t in json.load(sys.stdin)['active_tokens'] if t['scope']=='offer'][0])")
curl -s -X POST "http://localhost:3101/api/portal/offer/$OFFER_TOK?decision=accept"
```

Refresh the recruiter page — workflow advances to **Onboarding**, action ledger gains `workflow.completed`, no active tokens left.

---

## 8 · Recruiter view · the money shot

Linger on the **Recruiter** candidate page after the workflow completes. It's the single page that proves the value:

- **Header** — name, role, jurisdiction, current phase, **Download CV** link.
- **What we learned · cv_crystalliser** — canonical profile from the LLM extraction.
- **How the agent reasoned** — every `ocr_extract` call expanded with args + trimmed result, plus the final response.
- **Voice screening transcript** — turn-by-turn replay.
- **Audit timeline** — every orchestration step with timestamps. Look for `interview_invite`, `interview_booked`, `offer_decision`, `workflow.completed`.
- **Active magic links** — empty after onboarding (all tokens consumed or expired).

---

## 9 · Admin / Control-Plane view · 30 sec

On the **Admin** tab (`:5273`):

1. Find the hiring workflow in the list. Click in.
2. Header shows **type: hiring** with an **"Open recruiter view"** deep-link.
3. While at any of the three Phase 7 sub-waits, the page shows:
   > **Awaiting external party** *(gate ②)*
   > **Awaiting operator review** *(gates ① and ③)*

4. **Compare** by opening any expense workflow — wait label says *"Awaiting operator review"* and deep-link reads *"Open reviewer queue"*. **Zero hiring vocabulary** appears on the expense page. Platform-vs-domain split working.

---

## Reject paths

Re-run from step 1 with two more candidates to exercise the auto-rejection email:

- **Candidate B** (reject at gate ①): drive to `awaiting_interview_invite`, click **Reject** with optional reason. Workflow → `failed`. Email lands in `data/portal/email_outbox/` with subject `"Update on your <role> application"` and body `"After reviewing your screening for the <role> role, we've decided not to move forward at this stage."`

- **Candidate C** (reject at gate ③): drive all the way to `awaiting_interview_complete`, fill the form with **decision=Reject** + notes/rating, submit. Workflow → `failed`. Same email template, copy says `"After the interview stage we've decided not to move forward …"` instead.

The recruiter's free-text reason is **never** included in the candidate-facing email — it's logged only on the workflow ledger.

---

## TL;DR — record this in one take

```
Portal :5274        → apply (any synthetic PDF)              → ~5s
Recruiter           → click candidate, narrate LLM trace     → ~30s
                      (cv_crystalliser real OCR + reasoning)
Recruiter or curl   → fire voice transcript (real or fake)   → ~60s
Recruiter           → Gate ① panel: Invite to interview      → ~30s
Open /book          → Gate ②: pick a slot                    → ~30s
Recruiter           → Gate ③ panel: notes+rating+offer+level → ~60s
Admin :5273         → same workflow, point at neutral wait   → ~30s
                      labels + recruiter deep-link
curl /offer/accept  → workflow → Onboarding                  → ~10s
```

Total: **~5 minutes** smooth, **~8 minutes** with narration.

---

## Logs

<a id="logs"></a>

| Symptom | Where to look |
|---------|---------------|
| Apply returns 503 "blob storage unavailable" | Azurite isn't running. `tail logs/azurite.log` |
| Apply returns 404 "no workflow for role_id" | FastAPI didn't seed reqs. `tail logs/fastapi.log` for `seed_demo_reqs` |
| Triage panel stuck at "awaiting LLM run" | `tail -f logs/func.log` — look for `agent.completed` or `gh auth token` failure |
| Recruiter view 404 / loading forever | `curl http://localhost:3101/api/portal/admin/candidate/C-XXXXXXXX` — FastAPI side |
| Phase 7 gate panels not appearing | Check `awaiting_reason` matches one of `awaiting_interview_invite` / `awaiting_interview_booking` / `awaiting_interview_complete`. Hard-refresh portal Vite (Ctrl-Shift-R). |
| `/book?token=…` shows "Booking unavailable" 404 | Token was the wrong scope (e.g. you grabbed the `screen` token by mistake). Get the `book_interview` token from `/api/portal/admin/candidate/<CID>`. |
| Rejection email missing from outbox | Func host worker didn't pick up the orchestrator change. Restart func host: kill PID on 7071 then `cmd //c "scripts\\run-func.bat"`. |
| Admin view shows hiring strings on an expense workflow | Vite didn't HMR. Hard-refresh `:5273`. |

Restart Python services (keep Azurite + Vite warm):

```bash
# kill PIDs from `netstat -ano | findstr LISTENING | findstr ":3101 :7071"`
# then:
uv run uvicorn api.server.main:app --port 3101 > logs/fastapi.log 2>&1 &
cmd //c "scripts\\run-func.bat" > logs/func.log 2>&1 &
```
