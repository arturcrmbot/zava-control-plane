# Voice (real, via s2s accelerator) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the canned `acs-mcp` voice transcript path with a real browser-WebRTC voice screen powered by the user's existing speech-to-speech accelerator. Candidate portal route `/screen?token=xxx` mounts the accelerator. On call end, the accelerator POSTs transcript + score to the FastAPI `/api/portal/voice/{candidate_id}/transcript` endpoint, which raises the `voice_complete` external event on the Durable orchestration so Phase 6 resumes.

**Architecture:** Accelerator-as-black-box. We do NOT reimplement WebRTC, ACS dial, or GPT-Realtime. We mount the accelerator's UI component inside `/screen`, give it a webhook/callback URL, and resume the orchestration on the callback. The existing `acs-mcp` mock stays as a fallback for non-portal demos and tests that don't need the real path.

**Tech Stack:** Whatever the accelerator already uses. Most likely: React component, ACS SDK or LiveKit, GPT-Realtime over websockets, Web Audio API. FastAPI on the backend with a single new POST route.

**Master spec:** [docs/superpowers/specs/2026-04-30-poc1-poc2-demo-ready-design.md](../specs/2026-04-30-poc1-poc2-demo-ready-design.md) §5

---

## Phase 0 — Discovery (REQUIRED before any code)

The accelerator hasn't been examined yet. The user said it lives on their laptop and works. The first job is to read it and pin down the contract. Do NOT skip this phase.

### Task 0.1: Locate and read the accelerator

- [ ] **Ask the user for the accelerator path or repo URL.** Single question, terse — e.g., "What's the path to the speech-to-speech accelerator?" Wait for answer.

- [ ] **Read the top-level files.** `README.md`, `package.json`/`pyproject.toml`, entry points. Identify:
  - Frontend or full-stack? React component, full app, or library?
  - Voice transport? ACS, LiveKit, native WebRTC?
  - Model? GPT-Realtime via Azure OpenAI, OpenAI direct, Azure Speech?
  - Required env vars / credentials.
  - How a parent app embeds it (npm package import, iframe, copy source).

- [ ] **Identify the accelerator's "I'm done" hook.** Either:
  - It already supports a callback/webhook URL → we pass our `/api/portal/voice/.../transcript` endpoint and we're done with backend integration.
  - It only emits an `onCallEnd(transcript)` JS event → we add a thin wrapper that POSTs the transcript to our backend.
  - Something else → document in this plan as Task 0.4.

- [ ] **Identify Azure resource needs.** Does it need an ACS resource we provision? An Azure OpenAI deployment? Document.

### Task 0.2: Document the contract

- [ ] **Update this plan's "Phase 1 / Phase 2" tasks below with the actual API surface.** The remaining tasks are written assuming a generic shape and need concrete code once the accelerator is read.

- [ ] **Capture decisions inline:**
  - Mount strategy: copy / npm-link / git-submodule
  - Auth: magic-link token forwarded as `?token=` URL param vs separate auth
  - Transcript payload schema (fields, format, scoring)

- [ ] **Commit the discovery notes**

```
git commit -m "spec(voice): discovery of the s2s accelerator contract"
```

---

## Phase 1 — Backend integration

### Task 1: Voice transcript callback route (TDD)

**Files:**
- Create: `api/server/routes/portal_voice.py`
- Test: `tests/api/server/routes/test_portal_voice.py`
- Modify: `api/server/main.py`

- [ ] **Step 1: Write tests**

```python
# tests/api/server/routes/test_portal_voice.py
import pytest
from fastapi.testclient import TestClient
from api.server.main import app

def test_transcript_callback_raises_voice_complete(monkeypatch):
    raised: list[tuple[str, str, dict]] = []
    async def fake_raise(instance_id, event_name, payload):
        raised.append((instance_id, event_name, payload))
    monkeypatch.setattr("api.server.routes.portal_voice.raise_orchestration_event", fake_raise)
    # arrange: candidate exists with workflow_id + instance_id, magic link issued for scope=screen
    ...
    client = TestClient(app)
    resp = client.post(
        "/api/portal/voice/C-XYZ/transcript",
        json={"token": "<screen-token>", "transcript": [...], "score": 7.8, "duration_s": 124},
    )
    assert resp.status_code == 200
    assert raised[0][1] == "voice_complete"
    assert raised[0][2]["score"] == 7.8

def test_transcript_callback_404_on_unknown_candidate():
    ...

def test_transcript_callback_403_on_invalid_token():
    ...
```

- [ ] **Step 2: Run tests; verify FAIL**

- [ ] **Step 3: Implement the route**

```python
# api/server/routes/portal_voice.py
"""Accelerator → FastAPI callback after a voice screen call ends.

The accelerator POSTs the call transcript + score; we validate the magic-link
token, persist the transcript on the workflow, and raise the `voice_complete`
external event on the Durable orchestration so Phase 6 resumes.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.server.services.durable_client import raise_orchestration_event
from api.server.services.magic_link import MagicLinkExpired, MagicLinkAlreadyConsumed
from api.server.state import app_state

router = APIRouter(prefix="/api/portal/voice")


class TranscriptPayload(BaseModel):
    token: str
    transcript: list[dict]   # [{role: "agent"|"candidate", text: str, ts: float}, ...]
    score: float
    duration_s: float


@router.post("/{candidate_id}/transcript")
async def receive_transcript(candidate_id: str, body: TranscriptPayload):
    try:
        payload = app_state.magic_links.consume(body.token, scope="screen")
    except (MagicLinkExpired, MagicLinkAlreadyConsumed, ValueError):
        raise HTTPException(403, "invalid token")
    if payload["candidate_id"] != candidate_id:
        raise HTTPException(403, "token/candidate mismatch")

    candidate = app_state.store.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(404, "unknown candidate")
    instance_id = candidate.get("instance_id")
    if instance_id is None:
        raise HTTPException(409, "candidate has no orchestration instance")

    # persist transcript on workflow ledger for the audit trail
    app_state.store.append_voice_transcript(candidate["workflow_id"], candidate_id, body.dict())

    # raise the durable event — Phase 6 voice graph is suspended on this
    await raise_orchestration_event(instance_id, "voice_complete", {
        "candidate_id": candidate_id,
        "score": body.score,
        "duration_s": body.duration_s,
    })
    return {"ok": True}
```

- [ ] **Step 4: Register the route in `main.py`** and add `app_state.store.append_voice_transcript` (sibling of existing append methods).

- [ ] **Step 5: Run tests; verify PASS**

- [ ] **Step 6: Commit**

```
git commit -m "feat(voice): /api/portal/voice/{id}/transcript callback route"
```

### Task 2: Phase 6 voice graph waits for `voice_complete`

**Files:** `api/functions/graphs/voice.py`

- [ ] **Step 1: Read the current voice graph**

Run: `Read api/functions/graphs/voice.py`. Identify where it currently calls `acs_dial` against the `acs-mcp` mock. The graph likely has a single executor that returns the canned transcript synchronously.

- [ ] **Step 2: Modify Phase 6 to suspend on `voice_complete`**

The existing `wait_for_external_event` race-against-timer pattern from `expense_claim.py` Phase 5/6 is the model. The orchestration should:

1. Issue a `screen`-scope magic link for the candidate via a small new Durable activity (`activity_issue_screen_link`).
2. Send the candidate an email with the call link → `{PORTAL_BASE_URL}/screen?token={token}`.
3. `wait_for_external_event("voice_complete")` raced against a 24h timer.
4. On callback: read score from the event payload, apply the existing scoring rubric, emit verdict.
5. On timeout: emit `voice_screen_timeout` exception.

```python
# api/functions/graphs/voice.py — sketch (concrete code lands once the read is done)
def voice_graph(context, candidate):
    token = yield context.call_activity("activity_issue_screen_link", {"candidate_id": candidate["id"]})
    yield context.call_activity("activity_send_screen_email", {"candidate_id": candidate["id"], "token": token})

    deadline = context.current_utc_datetime + timedelta(hours=24)
    timeout_task = context.create_timer(deadline)
    callback_task = context.wait_for_external_event("voice_complete")
    winner = yield context.task_any([callback_task, timeout_task])

    if winner is timeout_task:
        return {"verdict": "timeout"}
    timeout_task.cancel()
    return apply_screening_rubric(winner.result)
```

- [ ] **Step 3: Add the two new activities** in `api/functions/workflows/activities.py`:
  - `activity_issue_screen_link(candidate_id) -> token`
  - `activity_send_screen_email(candidate_id, token) -> None`

- [ ] **Step 4: Update tests for the voice graph** — must verify the suspend/resume pattern.

- [ ] **Step 5: Commit**

```
git commit -m "feat(voice): Phase 6 graph suspends on voice_complete external event"
```

---

## Phase 2 — Frontend mount

### Task 3: Implement `/screen` route in the portal

**Files:** `web/portal/src/routes/Screen.tsx`, plus any accelerator-import wiring

The exact shape depends on Phase 0 discovery. Three branches:

**Branch A — accelerator is an npm package**

- [ ] Install: `cd web/portal && npm install @user/voice-accelerator`

- [ ] Mount:

```tsx
import { CallSurface } from "@user/voice-accelerator";

export default function Screen() {
  const token = new URLSearchParams(location.search).get("token")!;
  return <CallSurface
    callbackUrl={`/api/portal/voice/${candidateId}/transcript`}
    callbackPayloadExtras={{ token }}
    onEnd={() => location.assign(`/portal?token=${token}`)}
  />;
}
```

**Branch B — accelerator is source we copy**

- [ ] Copy the React component(s) into `web/portal/src/voice/`.

- [ ] Import + mount as in branch A.

**Branch C — accelerator is a separate app on its own port**

- [ ] Embed via `<iframe src="http://localhost:5180/?token=..." />` with explicit `postMessage` for the on-end signal.

- [ ] On `message` event, POST the transcript to our backend (since the iframe can't reach the parent's auth context cleanly).

### Task 4: Look up `candidateId` from the screen-scope token

**Files:** `web/portal/src/routes/Screen.tsx`, `web/portal/src/lib/api.ts`

- [ ] On mount, GET `/api/portal/screen-resolve?token=...` (new lightweight backend route — same pattern as status but only returns `candidate_id` without consuming the token).

- [ ] Pass `candidate_id` to the accelerator component.

- [ ] **Backend route** in `routes/portal_voice.py`:

```python
@router.get("/screen-resolve")
async def screen_resolve(token: str):
    # peek without consuming
    row = app_state.magic_links.peek(token, scope="screen")
    if row is None:
        raise HTTPException(404)
    return {"candidate_id": row["candidate_id"]}
```

(Add `MagicLinkStore.peek(token, scope)` — read without updating consumed_at.)

- [ ] **Step 5: Commit**

```
git commit -m "feat(voice): /screen route mounts s2s accelerator and POSTs transcript"
```

---

## Phase 3 — Demo robustness

### Task 5: Demo-mode toggle (real vs canned)

**Files:** `api/server/routes/portal_voice.py`, env

- [ ] **Step 1: Add env var `VOICE_TRANSPORT`** with values `accelerator` (default) | `canned`.

- [ ] **Step 2: When `VOICE_TRANSPORT=canned`**, the `/screen` route shows a single button "Run canned screen" that posts the existing `acs-mcp` mock's canned transcript to the same callback URL — preserves the demo if the accelerator flakes.

- [ ] **Step 3: Document in `docs/poc2-DEMO.md` §3 (Failure surfaces)**

```
| acs accelerator unreachable | Browser fails to reach the accelerator endpoint | Set VOICE_TRANSPORT=canned and redo the call from /screen — same transcript flow, just stubbed audio. |
```

- [ ] **Step 4: Commit**

```
git commit -m "feat(voice): VOICE_TRANSPORT=canned fallback for demo robustness"
```

---

## Acceptance criteria

- [ ] Phase 0 discovery notes captured in this plan and committed
- [ ] `/api/portal/voice/{candidate_id}/transcript` accepts the accelerator's POST and raises `voice_complete` on the orchestration
- [ ] Phase 6 voice graph suspends on `voice_complete` and resumes with the score
- [ ] `web/portal/src/routes/Screen.tsx` mounts the accelerator's UI; the demoer can complete a call and see the workflow advance from Phase 6 → Phase 7
- [ ] `VOICE_TRANSPORT=canned` falls back to the existing `acs-mcp` mock without code changes

## Out of scope

- New voice-screening logic, rubric, or skill prompts (the existing `voice-screener` skill is reused)
- Multi-language voice (single-locale demo)
- Real PSTN inbound (we explicitly chose browser WebRTC at brainstorming Q3=C)
- Recording / playback of past calls (transcript is enough for the audit trail)

## Dependencies on other streams

- **Candidate portal stream** owns `web/portal/` scaffold and the `/screen` route file. This stream fills the route content. Coordinate with portal stream so Vite scaffold lands first.
- **HeyGen stream** is independent.
- **AG-UI render stream** is independent.
- **POC1 corpus run stream** is independent.
