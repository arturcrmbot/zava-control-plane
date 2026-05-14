# 2026-05-01 — Recruiter HITL: post-voice + post-interview gates

## Goal

Replace the current Voice → (auto) → Offer jump with two recruiter-gated decisions and a candidate-driven interview booking step. The AI recommends; the recruiter decides. Mirrors how a real recruiting flow works — and gives us a third surface for the demo (recruiter doing meaningful work, not just observing).

## Today's flow vs new flow

**Today** (`api/functions/workflows/hiring.py`):
```
Voice (candidate HITL)
  → Interview (stub agent — no human)
  → Compliance (agent)
  → Offer (candidate accept/decline HITL)
  → Onboarding
```

**New**:
```
Voice (candidate HITL — unchanged)
  → Interview (current_phase): three sequential waits
      ① awaiting_interview_invite     (operator_review)  ← recruiter
      ② awaiting_interview_booking    (external_party)   ← candidate picks slot
      ③ awaiting_interview_complete   (operator_review)  ← recruiter
  → Compliance (agent — unchanged)
  → Offer (candidate accept/decline HITL — unchanged)
  → Onboarding
```

`current_phase` stays `Interview` across all three sub-waits; `awaiting_reason` + `wait_kind` differentiate them. The admin/Control-Plane already renders neutral copy off `wait_kind` (operator_review vs external_party) per the platform contract.

## New durable events

| Event name             | Raised by                                      | Resumes orchestrator from         |
|------------------------|------------------------------------------------|------------------------------------|
| `interview_invite`     | `POST /api/portal/admin/candidate/{id}/interview-invite` | `awaiting_interview_invite`        |
| `interview_booked`     | `POST /api/portal/interview/book`              | `awaiting_interview_booking`       |
| `offer_decision`       | `POST /api/portal/admin/candidate/{id}/post-interview-decision` | `awaiting_interview_complete` |

Existing event names retained: `voice_complete`, `offer_approval` (candidate's accept/decline), `budget_approval`.

## Magic-link scopes

One new scope alongside `status` / `screen` / `offer`:

| Scope            | TTL    | single_use | Purpose                                  |
|------------------|--------|------------|------------------------------------------|
| `book_interview` | 7 days | yes        | Candidate's `/book?token=…` booking link |

`magic_link.py` doesn't need a schema change — scope is a free-text column.

## New components

### Agent — `interview-recommender`

**Skill**: `api/server/skills/interview-recommender/SKILL.md`. Frontmatter `allowed-tools:` empty (pure reasoning, no tool calls). Loaded via `_wrapper.run_agent_session`.

**Executor**: `api/functions/graphs/executors/agents/agent_interview_recommender.py` — mirrors `agent_cv_crystalliser.py` shape (build prompt from input dict, call wrapper, return dict). Same `agent.completed` webhook → `agent_reasoning` ledger flow already wired.

**Input shape** (passed in the activity payload, agent reads from prompt):
- Always: `cv_crystalliser` profile, `screening` verdict, `voice_transcript[]`, `voice_score`, `role_title`.
- The recommender runs at gates ① and ③ only (gate ② is the candidate's booking wait — no recruiter action, no agent call). At gate ③ it does **not** see interview notes — recruiter writes notes after seeing the rec, and notes are metadata on the human's decision rather than input to a second AI call.

**Output JSON contract** (single shape for both gates):
```json
{
  "decision": "advance" | "decline",
  "level_suggestion": "Senior" | null,
  "rationale": "…2-3 sentences…",
  "talking_points": ["probe X", "verify Y"]
}
```

`level_suggestion` is `null` at gate ① (interview not done yet); populated at gate ③.

**Failure mode**: agent call fails → recruiter sees the trace's error in the panel but can still act. Don't gate on AI.

### Activities (new entries in `api/functions/workflows/activities.py`)

- `hiring_interview_recommender_activity_trigger` — runs the agent. Called twice in the orchestrator (gate ① and gate ③).
- `issue_book_interview_link_activity_trigger` — issues the `book_interview` magic link. Returns `{token, portal_url}`.
- `send_book_interview_email_activity_trigger` — renders + sends booking email via `app_state.email_sender`.
- `send_rejection_email_activity_trigger` — renders + sends polite rejection email. Takes `gate: "interview" | "offer"` so the copy can differ slightly.

### Backend routes

`api/server/routes/portal_interview.py` (new file):

- `GET  /api/portal/interview/resolve?token=…` — peek `book_interview` token. Returns `{candidate_id, role_title, slots: SlotGrid}`. Mirrors `/api/portal/voice/screen-resolve`.
- `POST /api/portal/interview/book` — body `{token, slot_id}`. Consumes the token, persists `interview_slot` on candidate dict, raises `interview_booked` Durable event with the slot.

Recruiter actions added to `api/server/routes/portal.py` (or a sibling `portal_admin.py` if it gets fat):

- `POST /api/portal/admin/candidate/{id}/interview-invite` — body `{decision: "invite"|"reject", reason?: string}`. Raises `interview_invite`. On reject also schedules the rejection email activity.
- `POST /api/portal/admin/candidate/{id}/post-interview-decision` — body `{decision: "offer"|"reject", level?: string, notes: string, rating: 1..5, reason?: string}`. Raises `offer_decision` with the full payload. Notes + rating get appended to the workflow's action_ledger.

### Slot grid (mock calendar)

5 weekdays × 3 slots/day = 15 candidate slot rows. Slot times: 09:00, 13:00, 16:00 local (string, no tz math). "Available" mask is `hash(candidate_id + slot_id) % 5 != 0` — deterministic per candidate, ~80% available, every candidate sees a different (but stable) pattern. Past dates are always unavailable.

The mask is computed server-side in `/resolve` so the same dates roll forward without persisting calendar state.

### Levels by role family

`api/shared/role_levels.py` (new tiny module):
```python
LEVELS_BY_ROLE_FAMILY = {
    "Data Engineering":  ["Mid-Level", "Senior", "Staff", "Principal"],
    "Creative":          ["Director", "Senior Director", "VP Creative"],
}
DEFAULT_LEVELS = ["Junior", "Mid", "Senior", "Lead"]
```

Recruiter form's level dropdown options come from this. The agent's `level_suggestion` is shown in the AI rec card as a hint but does NOT pre-fill the dropdown unless it matches a value in the set — the recruiter always picks explicitly.

### Frontend

`web/portal/src/routes/Book.tsx` (new) — slot grid + submit.

`web/portal/src/routes/RecruiterCandidate.tsx` grows three conditional panels keyed off `workflow.awaiting_reason`:
- `awaiting_interview_invite` → "Decision: invite to interview" panel: AI rec card + Invite/Reject buttons + optional reject-reason textarea.
- `awaiting_interview_booking` → "Awaiting candidate to book" panel: shows the candidate's `/book` URL (operator copy-paste fallback) + active `book_interview` token from `active_tokens`.
- `awaiting_interview_complete` → "Post-interview decision" form: AI rec card + notes textarea + 1-5 rating + decision radio + level dropdown + submit.

Each panel renders the latest `interview-recommender` entry from `agent_reasoning` (filter by `agent_label === "interview_recommender"`). Existing renderer for tool-call/response collapsibles is reused.

`web/portal/src/lib/api.ts` adds: `postInterviewDecision`, `postPostInterviewDecision`, `getBookingResolve`, `postBooking`.

### Email templates

Three new render functions in `portal_orchestration.py` (or split out into `email_templates.py` if the file grows):
- `_render_book_interview_email(name, role_title, book_url)` — "Great chat earlier — pick a time below to meet the team."
- `_render_rejection_email(name, role_title, gate)` — "Thanks for your time — we won't be moving forward at this stage." Single template; the `gate` arg only changes one sentence.

## Data flow at gate ③ (the trickiest one)

1. Candidate books slot → `interview_booked` event → orchestrator transitions to `awaiting_interview_complete`.
2. Orchestrator immediately calls `hiring_interview_recommender_activity_trigger`. Agent runs against `cv_crystalliser + screening + voice_transcript + role_title` (no interview notes — recruiter hasn't written them).
3. Webhook bridge persists `interview-recommender` reasoning entry on the workflow.
4. Recruiter polls the candidate detail page (8s refresh), sees the AI rec card.
5. Recruiter conducts interview offline (Teams etc.).
6. Recruiter returns to the page, fills the post-interview form (notes, rating, decision, level), submits.
7. POST `/post-interview-decision` raises `offer_decision` with the full payload. Notes + rating land on the action ledger; level + decision drive the orchestrator's branch.
8. If `decision=offer` → resume to Compliance. If `decline` → schedule rejection email + workflow.rejected.

The agent **does not** see interview notes. Notes are recorded as metadata on the human's decision, not as input to a second AI call. We could re-run the recommender after notes are submitted as a "validate the recruiter's call against the transcript" check, but that's out of scope for v1.

## Error handling

| Failure                                          | Behaviour                                                         |
|--------------------------------------------------|-------------------------------------------------------------------|
| `interview-recommender` LLM call fails           | Trace recorded with error; recruiter still sees the panel + can act unblocked. |
| Candidate clicks expired booking link            | `/book` page renders "this booking link has expired — contact the recruiter". |
| Recruiter clicks Reject without reason           | Reason optional. Empty reason → ledger note says "no reason given". |
| Post-interview form submitted with offer + no level | 400 from backend; form-level validation prevents the click anyway. |
| Booking timeout (7d, candidate never books)      | Orchestrator timer race → `workflow.completed (timeout)`. Same pattern as voice timeout today. |
| Post-interview wait timeout (5d, recruiter never returns) | Same pattern. Workflow auto-closes. |
| Candidate POSTs `/book` with already-consumed token | 403, page says "this slot was already booked". |

## Testing

**Unit**:
- `agent_interview_recommender.execute()` given fixture inputs → expected JSON shape.
- `portal_interview.book()` consumes token + raises event (mock `raise_orchestration_event`).
- Both admin recruiter-decision endpoints raise the right event with the right payload.
- Slot mask is deterministic per candidate.

**Integration**:
- Full happy path: voice_complete → interview_invite=invite → interview_booked → offer_decision=offer → reaches Phase 8 Compliance.
- Reject at gate ①: rejection email called, workflow.rejected, no booking link issued.
- Reject at gate ③: rejection email called, workflow.rejected, no Compliance phase entered.
- Booking timeout: timer wins race, workflow.completed (timeout).

**Smoke**:
- E2E via the recruiter view in the running portal: apply → triage → voice → invite → book → record → offer → accept. Each gate paints the right panel.

## Out of scope

- Real calendar integration (Outlook/Google). Slots are a deterministic mock.
- Real Teams meeting creation. We assume the meeting happens; the recruiter manages it offline.
- Compensation negotiation. Offer letter still uses the existing fixed-template path; the recruiter's `level` becomes a workflow-metadata field but doesn't drive comp.
- Re-running the recommender after notes are recorded ("did the recruiter's call match the AI's read of the data?").
- Variable interview panels / multiple interviewers. Single recruiter, single interview.

## Migration

The current `hiring_interview_activity_trigger` in `activities.py` and the `build_hiring_interview_workflow` graph in `graphs/interview.py` are stub-only — no real outputs are consumed downstream. Safe to remove and replace with the new activity sequence.

No data-store migrations: candidate dict already accepts arbitrary keys (we add `interview_slot`, `interview_notes`, `interview_rating`, `interview_decision`, `level`); workflow's `action_ledger` already accepts arbitrary entries.

## Surface inventory

| Surface           | Change                                                                                  |
|-------------------|-----------------------------------------------------------------------------------------|
| Orchestrator      | Replace stub Phase 7 with three-wait sequence.                                          |
| Activities        | +4 new activity functions.                                                              |
| Skills            | +1 new skill: `interview-recommender/SKILL.md`.                                         |
| Agents            | +1 new executor: `agent_interview_recommender.py`.                                      |
| Backend routes    | +1 new file `portal_interview.py`; +2 new admin routes in `portal.py`.                  |
| Magic-link scope  | +`book_interview`.                                                                      |
| Email templates   | +2 (booking, rejection).                                                                |
| Frontend routes   | +1 `/book` route.                                                                       |
| Recruiter view    | +3 conditional panels.                                                                  |
| Constants         | +`api/shared/role_levels.py`.                                                           |
| Admin shell       | No changes — wait_kind contract already covers the new operator_review waits.           |
