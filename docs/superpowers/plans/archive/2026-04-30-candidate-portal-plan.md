# Candidate Portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** New `web/portal/` Vite app with three routes (`/apply`, `/portal?token=xxx`, `/screen?token=xxx`), backend `/api/portal/*` routes, magic-link auth issued via real ACS Email + admin-UI fallback, plus services for blob upload, email send, and magic-link state.

**Architecture:** Separate Vite app under `web/portal/` (own build, own deploy). FastAPI gains a `routes/portal.py` for public + token-authed endpoints. New services: `magic_link.py` (sqlite-backed token store with single-use semantics), `email_send.py` (ACS Email REST), `blob_store.py` (Azure Blob upload via `azure-storage-blob`). Apply submission attaches the candidate to an existing `HiringOrchestrator` workflow keyed by `role_id` and fires `candidate.applied` to trigger Phase 4 Triage.

**Tech Stack:** React + Vite + TypeScript + Tailwind (mirrors `web/client/`), FastAPI, sqlite (via `sqlite3` stdlib), `azure-storage-blob`, `httpx` for ACS Email REST.

**Master spec:** [docs/superpowers/specs/2026-04-30-poc1-poc2-demo-ready-design.md](../specs/2026-04-30-poc1-poc2-demo-ready-design.md) §4

---

## File Structure

**New files:**

```
web/portal/                              # NEW Vite app
├── package.json                         # depends on react, react-router-dom, vite, tailwind
├── vite.config.ts                       # proxy /api → http://localhost:8000
├── tailwind.config.cjs
├── index.html
└── src/
    ├── main.tsx                         # React root, router setup
    ├── App.tsx                          # candidate-friendly shell (no admin chrome)
    ├── routes/
    │   ├── Apply.tsx                    # public form: role dropdown, name, email, CV PDF
    │   ├── Portal.tsx                   # /portal?token=xxx — phase-aware status page
    │   └── Screen.tsx                   # /screen?token=xxx — placeholder for voice stream's <ScreenCall/> component
    ├── components/
    │   ├── PhaseProgress.tsx            # 10-phase ribbon, candidate-friendly labels
    │   ├── OfferPanel.tsx               # Accept/Decline buttons + offer letter PDF preview
    │   └── OnboardingPanel.tsx          # video player slot for HeyGen mp4 (URL only — voice stream owns Screen.tsx)
    ├── lib/
    │   └── api.ts                       # typed fetch wrapper (POST apply, GET portal status, etc.)
    └── styles.css

api/server/routes/portal.py              # NEW — public + magic-link routes
api/server/services/magic_link.py        # NEW — sqlite-backed token store
api/server/services/email_send.py        # NEW — ACS Email REST sender
api/server/services/blob_store.py        # NEW — Azure Blob client wrapper (CVs + later HeyGen mp4s)

tests/api/server/services/test_magic_link.py
tests/api/server/services/test_email_send.py
tests/api/server/services/test_blob_store.py
tests/api/server/routes/test_portal.py
tests/web/portal/Apply.test.tsx
tests/web/portal/Portal.test.tsx
```

**Modified files:**

- `api/server/main.py` — register `portal_router`
- `api/server/state.py` — add `app_state.magic_links` (MagicLinkStore singleton)
- `api/shared/events.py` — add `candidate.applied`, `magic_link.issued`, `offer.decided` events
- `api/server/services/state_store.py` — `attach_candidate(workflow_id, candidate)` method
- `package.json` (root) — add `dev:portal` and `build:portal` scripts
- `.env.example` — `ACS_EMAIL_CONNECTION_STRING`, `ACS_EMAIL_SENDER_ADDRESS`, `AZURE_STORAGE_CONNECTION_STRING`, `PORTAL_BASE_URL`

---

## Task 1: Magic-link service (TDD)

**Files:**
- Create: `api/server/services/magic_link.py`
- Test: `tests/api/server/services/test_magic_link.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/server/services/test_magic_link.py
import time
import pytest
from api.server.services.magic_link import MagicLinkStore, MagicLinkExpired, MagicLinkAlreadyConsumed

def test_issue_returns_url_safe_32_char_token(tmp_path):
    store = MagicLinkStore(db_path=tmp_path / "t.sqlite")
    token = store.issue(candidate_id="C-1", scope="screen", ttl_seconds=60)
    assert len(token) == 32
    assert token.isascii()

def test_consume_within_ttl_returns_payload(tmp_path):
    store = MagicLinkStore(db_path=tmp_path / "t.sqlite")
    token = store.issue(candidate_id="C-1", scope="screen", ttl_seconds=60)
    payload = store.consume(token, scope="screen")
    assert payload["candidate_id"] == "C-1"

def test_consume_after_expiry_raises(tmp_path):
    store = MagicLinkStore(db_path=tmp_path / "t.sqlite")
    token = store.issue(candidate_id="C-1", scope="screen", ttl_seconds=0)
    time.sleep(0.05)
    with pytest.raises(MagicLinkExpired):
        store.consume(token, scope="screen")

def test_consume_twice_for_single_use_scope_raises(tmp_path):
    store = MagicLinkStore(db_path=tmp_path / "t.sqlite")
    token = store.issue(candidate_id="C-1", scope="offer", ttl_seconds=60, single_use=True)
    store.consume(token, scope="offer")
    with pytest.raises(MagicLinkAlreadyConsumed):
        store.consume(token, scope="offer")

def test_repeatable_read_scope_can_consume_many_times(tmp_path):
    store = MagicLinkStore(db_path=tmp_path / "t.sqlite")
    token = store.issue(candidate_id="C-1", scope="status", ttl_seconds=60, single_use=False)
    store.consume(token, scope="status")
    store.consume(token, scope="status")  # no raise

def test_consume_with_wrong_scope_raises(tmp_path):
    store = MagicLinkStore(db_path=tmp_path / "t.sqlite")
    token = store.issue(candidate_id="C-1", scope="screen", ttl_seconds=60)
    with pytest.raises(ValueError, match="scope mismatch"):
        store.consume(token, scope="offer")

def test_list_active_for_admin_panel(tmp_path):
    store = MagicLinkStore(db_path=tmp_path / "t.sqlite")
    store.issue(candidate_id="C-1", scope="status", ttl_seconds=60)
    store.issue(candidate_id="C-2", scope="screen", ttl_seconds=60)
    rows = store.list_active()
    assert len(rows) == 2
    assert {r["candidate_id"] for r in rows} == {"C-1", "C-2"}
```

- [ ] **Step 2: Run tests; verify all FAIL**

Run: `uv run pytest tests/api/server/services/test_magic_link.py -v`
Expected: import error (module not yet created).

- [ ] **Step 3: Implement minimal `MagicLinkStore`**

```python
# api/server/services/magic_link.py
"""Sqlite-backed magic-link token store. Single-use semantics on offer-grade
scopes; repeatable read on status-grade scopes."""
from __future__ import annotations
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any


class MagicLinkExpired(Exception): ...
class MagicLinkAlreadyConsumed(Exception): ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    token TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    issued_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    single_use INTEGER NOT NULL,
    consumed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_active ON links(expires_at, consumed_at);
"""


class MagicLinkStore:
    def __init__(self, db_path: str | Path):
        self._path = str(db_path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._path, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def issue(self, *, candidate_id: str, scope: str, ttl_seconds: int, single_use: bool = True) -> str:
        token = secrets.token_urlsafe(24)[:32]
        now = time.time()
        with self._conn() as c:
            c.execute(
                "INSERT INTO links (token, candidate_id, scope, issued_at, expires_at, single_use) VALUES (?,?,?,?,?,?)",
                (token, candidate_id, scope, now, now + ttl_seconds, int(single_use)),
            )
        return token

    def consume(self, token: str, *, scope: str) -> dict[str, Any]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM links WHERE token=?", (token,)).fetchone()
            if row is None:
                raise ValueError("token not found")
            if row["scope"] != scope:
                raise ValueError(f"scope mismatch: token={row['scope']} requested={scope}")
            if time.time() > row["expires_at"]:
                raise MagicLinkExpired(token)
            if row["single_use"] and row["consumed_at"] is not None:
                raise MagicLinkAlreadyConsumed(token)
            if row["single_use"]:
                c.execute("UPDATE links SET consumed_at=? WHERE token=?", (time.time(), token))
            return {"candidate_id": row["candidate_id"], "scope": row["scope"]}

    def list_active(self) -> list[dict[str, Any]]:
        with self._conn() as c:
            now = time.time()
            rows = c.execute(
                "SELECT token, candidate_id, scope, issued_at, expires_at FROM links WHERE expires_at > ? AND consumed_at IS NULL ORDER BY issued_at DESC",
                (now,),
            ).fetchall()
            return [dict(r) for r in rows]
```

- [ ] **Step 4: Run tests; verify PASS**

Run: `uv run pytest tests/api/server/services/test_magic_link.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```
git add api/server/services/magic_link.py tests/api/server/services/test_magic_link.py
git commit -m "feat(portal): magic-link sqlite store with single-use + repeatable-read scopes"
```

---

## Task 2: Email-send service (ACS Email REST)

**Files:**
- Create: `api/server/services/email_send.py`
- Test: `tests/api/server/services/test_email_send.py`

- [ ] **Step 1: Read the ACS Email REST docs**

Use Context7: `mcp__plugin_context7_context7__resolve-library-id` for `azure-communication-email`, then fetch docs. Confirm REST shape: `POST /emails:send` against the ACS Email endpoint in the connection string.

- [ ] **Step 2: Write tests with mocked httpx**

```python
# tests/api/server/services/test_email_send.py
import pytest
import respx
import httpx
from api.server.services.email_send import EmailSender, EmailSendError

@pytest.fixture
def sender(tmp_path):
    return EmailSender(
        connection_string="endpoint=https://x.communication.azure.com/;accesskey=AAAA",
        sender_address="DoNotReply@demo.example",
        outbox_dir=tmp_path / "outbox",
    )

@respx.mock
def test_send_posts_to_acs_endpoint_and_returns_message_id(sender):
    respx.post("https://x.communication.azure.com/emails:send").mock(
        return_value=httpx.Response(202, json={"id": "msg-123"}, headers={"operation-location": "..."}),
    )
    msg_id = sender.send(to="alice@example.com", subject="Hi", html_body="<p>hi</p>")
    assert msg_id == "msg-123"
    assert (sender.outbox_dir / "msg-123.html").read_text() == "<p>hi</p>"

@respx.mock
def test_send_raises_on_4xx(sender):
    respx.post("https://x.communication.azure.com/emails:send").mock(return_value=httpx.Response(400, json={"error": "bad"}))
    with pytest.raises(EmailSendError):
        sender.send(to="alice@example.com", subject="Hi", html_body="<p>hi</p>")

def test_send_falls_back_to_outbox_when_unconfigured(tmp_path):
    sender = EmailSender(connection_string=None, sender_address=None, outbox_dir=tmp_path / "ob")
    msg_id = sender.send(to="alice@example.com", subject="Hi", html_body="<p>hi</p>")
    assert msg_id.startswith("local-")
    assert (sender.outbox_dir / f"{msg_id}.html").exists()
```

- [ ] **Step 3: Run tests; verify FAIL**

Run: `uv run pytest tests/api/server/services/test_email_send.py -v`
Expected: import error.

- [ ] **Step 4: Implement minimal `EmailSender`**

Decompose the connection string into endpoint + access key. Sign the request per ACS HMAC-SHA256 rules (date header + signed-headers list). Persist HTML to `outbox_dir/{message_id}.html` regardless of branch (real or fallback) so the demo can always inspect the email body.

```python
# api/server/services/email_send.py — implement per the ACS Email REST docs.
# Real-network branch: HMAC-sign the request, POST, return server message id.
# Fallback branch (connection_string is None): write to outbox, return f"local-{uuid}".
```

- [ ] **Step 5: Run tests; verify PASS**

Run: `uv run pytest tests/api/server/services/test_email_send.py -v`

- [ ] **Step 6: Commit**

```
git commit -m "feat(portal): ACS Email sender with offline outbox fallback"
```

---

## Task 3: Blob storage service

**Files:**
- Create: `api/server/services/blob_store.py`
- Test: `tests/api/server/services/test_blob_store.py`

- [ ] **Step 1: Add dependency**

Edit `pyproject.toml` to add `azure-storage-blob`. Run `uv sync`. Re-export `requirements.txt`.

- [ ] **Step 2: Write tests against Azurite (already running on :10000)**

```python
import pytest, os
from api.server.services.blob_store import BlobStore

CONN = os.environ.get(
    "AZURE_STORAGE_CONNECTION_STRING",
    "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
    "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
)

def test_put_and_get_url():
    bs = BlobStore(connection_string=CONN, container="test-portal")
    url = bs.put("cv-001.pdf", b"%PDF-1.4 ...", content_type="application/pdf")
    assert url.startswith("http://127.0.0.1:10000/devstoreaccount1/test-portal/cv-001.pdf")

def test_put_then_sas_url_with_ttl():
    bs = BlobStore(connection_string=CONN, container="test-portal")
    bs.put("video-x.mp4", b"\x00\x00\x00\x18ftyp", content_type="video/mp4")
    sas = bs.sas_url("video-x.mp4", ttl_seconds=300)
    assert "se=" in sas  # signed expiry
    assert "sig=" in sas
```

- [ ] **Step 3: Run tests; verify FAIL** (module missing)

- [ ] **Step 4: Implement `BlobStore`**

```python
# api/server/services/blob_store.py
from __future__ import annotations
import datetime as dt
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

class BlobStore:
    def __init__(self, *, connection_string: str, container: str):
        self._svc = BlobServiceClient.from_connection_string(connection_string)
        self._container = container
        try:
            self._svc.create_container(container)
        except Exception:
            pass

    def put(self, name: str, data: bytes, *, content_type: str) -> str:
        client = self._svc.get_blob_client(self._container, name)
        client.upload_blob(data, overwrite=True, content_type=content_type)
        return client.url

    def sas_url(self, name: str, *, ttl_seconds: int) -> str:
        client = self._svc.get_blob_client(self._container, name)
        cred = self._svc.credential
        sas = generate_blob_sas(
            account_name=client.account_name,
            container_name=self._container,
            blob_name=name,
            account_key=cred.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=dt.datetime.utcnow() + dt.timedelta(seconds=ttl_seconds),
        )
        return f"{client.url}?{sas}"

    def exists(self, name: str) -> bool:
        return self._svc.get_blob_client(self._container, name).exists()
```

- [ ] **Step 5: Run tests; verify PASS**

(Azurite must be running locally on :10000. Skip with `pytest -k blob_store --no-header` if Azurite is down.)

- [ ] **Step 6: Commit**

```
git commit -m "feat(portal): Azure Blob storage service with SAS-URL helper"
```

---

## Task 4: New event types

**Files:** Modify `api/shared/events.py`

- [ ] **Step 1: Add the three new event-type constants and dataclass shapes**

```python
# api/shared/events.py — extend the existing FleetEvent type union or string-event registry
EVENT_CANDIDATE_APPLIED = "candidate.applied"
EVENT_MAGIC_LINK_ISSUED = "magic_link.issued"
EVENT_OFFER_DECIDED = "offer.decided"
```

- [ ] **Step 2: If FleetEvent is dataclass-shape, add typed fields** (`candidate_id`, `magic_token`, `offer_decision`).

- [ ] **Step 3: Run existing event tests** (`uv run pytest tests/api/shared/test_events.py -v`) — ensure no regressions.

- [ ] **Step 4: Commit**

```
git commit -m "feat(portal): three new candidate-flow event types"
```

---

## Task 5: Backend route — POST /api/portal/apply

**Files:**
- Create: `api/server/routes/portal.py`
- Test: `tests/api/server/routes/test_portal.py`
- Modify: `api/server/main.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/server/routes/test_portal.py
import io
from fastapi.testclient import TestClient
from api.server.main import app

def test_apply_creates_candidate_and_attaches_to_workflow():
    client = TestClient(app)
    pdf_bytes = b"%PDF-1.4 fake"
    resp = client.post(
        "/api/portal/apply",
        data={"role_id": "REQ-SDE-USA-DEMO", "name": "Alice Engineer", "email": "alice@example.com"},
        files={"cv": ("alice.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "submitted"
    assert body["candidate_id"].startswith("C-")
```

- [ ] **Step 2: Run test; verify FAIL** (route not registered)

- [ ] **Step 3: Implement the route**

```python
# api/server/routes/portal.py
from __future__ import annotations
import os, uuid
from fastapi import APIRouter, UploadFile, Form, HTTPException
from api.server.state import app_state
from api.shared.events import FleetEvent, EVENT_CANDIDATE_APPLIED

router = APIRouter(prefix="/api/portal")


@router.post("/apply", status_code=202)
async def apply(
    role_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    cv: UploadFile = ...,
):
    if cv.content_type != "application/pdf":
        raise HTTPException(415, "cv must be application/pdf")
    cv_bytes = await cv.read()
    candidate_id = f"C-{uuid.uuid4().hex[:8].upper()}"
    cv_blob_name = f"cvs/{candidate_id}.pdf"
    cv_url = app_state.blob_store.put(cv_blob_name, cv_bytes, content_type="application/pdf")
    candidate = {"id": candidate_id, "name": name, "email": email, "cv_url": cv_url, "role_id": role_id}
    workflow_id = app_state.store.attach_candidate_to_role(role_id, candidate)
    if workflow_id is None:
        raise HTTPException(404, f"no workflow for role_id={role_id}")
    app_state.bus.emit(FleetEvent(type=EVENT_CANDIDATE_APPLIED, workflow_id=workflow_id, candidate_id=candidate_id))
    return {"status": "submitted", "candidate_id": candidate_id, "workflow_id": workflow_id}
```

- [ ] **Step 4: Wire `app_state.blob_store` and `attach_candidate_to_role` in state startup; register router in `main.py`**

```python
# api/server/main.py — under existing route registrations
from api.server.routes.portal import router as portal_router
app.include_router(portal_router)
```

- [ ] **Step 5: Run test; verify PASS**

- [ ] **Step 6: Commit**

```
git commit -m "feat(portal): POST /api/portal/apply — CV intake + candidate.applied event"
```

---

## Task 6: Backend route — GET /api/portal/status (token-authed)

**Files:** `api/server/routes/portal.py`

- [ ] **Step 1: Write tests for happy path + invalid token + expired token**

```python
def test_status_returns_workflow_phase_for_valid_token():
    # arrange a workflow + a token
    ...

def test_status_404_on_invalid_token():
    ...

def test_status_410_on_expired_token():
    ...
```

- [ ] **Step 2: Implement**

```python
@router.get("/status/{token}")
async def status(token: str):
    try:
        payload = app_state.magic_links.consume(token, scope="status")
    except MagicLinkExpired:
        raise HTTPException(410, "link expired")
    except ValueError:
        raise HTTPException(404, "invalid token")
    candidate = app_state.store.get_candidate(payload["candidate_id"])
    workflow = app_state.store.get_workflow(candidate["workflow_id"])
    return {
        "candidate": candidate,
        "phase": workflow.current_phase,
        "next_action": workflow.next_action,  # "rsvp_screening" | "rsvp_interview" | "decide_offer" | None
        "offer_letter_url": workflow.offer_letter_url if workflow.current_phase == "offer" else None,
        "onboarding_video_url": workflow.onboarding_video_url if workflow.current_phase == "onboarding" else None,
    }
```

- [ ] **Step 3: Run, verify, commit**

```
git commit -m "feat(portal): GET /api/portal/status/{token} — phase-aware candidate view"
```

---

## Task 7: Backend route — POST /api/portal/offer/{token}

**Files:** `api/server/routes/portal.py`

- [ ] **Step 1: Tests for accept + decline + double-consume rejection**

- [ ] **Step 2: Implement**

```python
@router.post("/offer/{token}")
async def decide_offer(token: str, decision: str):
    if decision not in {"accept", "decline"}:
        raise HTTPException(400, "decision must be accept|decline")
    try:
        payload = app_state.magic_links.consume(token, scope="offer")  # single-use
    except MagicLinkAlreadyConsumed:
        raise HTTPException(409, "already decided")
    except (MagicLinkExpired, ValueError):
        raise HTTPException(404, "invalid or expired")
    candidate = app_state.store.get_candidate(payload["candidate_id"])
    await raise_orchestration_event(candidate["instance_id"], "offer_decision", {"decision": decision})
    app_state.bus.emit(FleetEvent(type=EVENT_OFFER_DECIDED, workflow_id=candidate["workflow_id"], candidate_id=candidate["id"], offer_decision=decision))
    return {"ok": True, "decision": decision}
```

- [ ] **Step 3: Run, verify, commit**

---

## Task 8: Triage trigger on `candidate.applied`

**Files:** Modify `api/functions/graphs/triage.py` and/or `api/server/services/exception_factory.py`

- [ ] **Step 1: Find where Triage Phase 4 currently fires**

Run: `Grep "phase.*triage" --type py`. Identify whether it's auto-fired on workflow start or per-candidate.

- [ ] **Step 2: Wire `candidate.applied` to invoke Triage for the new candidate**

Subscribe in `online_subscriber.py` or in a new `routes/portal_orchestration.py` that pulls events and POSTs to `/internal/durable-event` with the candidate-specific kwargs.

- [ ] **Step 3: When Triage finishes**, if shortlist score ≥ threshold → issue magic link + send email:

```python
def on_triage_complete(workflow_id, candidate_id, score):
    if score < SHORTLIST_THRESHOLD:
        return
    token = app_state.magic_links.issue(candidate_id=candidate_id, scope="status", ttl_seconds=7*24*3600, single_use=False)
    portal_url = f"{os.environ['PORTAL_BASE_URL']}/portal?token={token}"
    candidate = app_state.store.get_candidate(candidate_id)
    app_state.email_sender.send(
        to=candidate["email"],
        subject="Your application — next steps",
        html_body=render_template("magic_link_issued.html", name=candidate["name"], portal_url=portal_url),
    )
    app_state.bus.emit(FleetEvent(type=EVENT_MAGIC_LINK_ISSUED, candidate_id=candidate_id, magic_token=token))
```

- [ ] **Step 4: Tests + commit**

---

## Task 9: Vite scaffold for `web/portal/`

**Files:** Everything under `web/portal/`

- [ ] **Step 1: Bootstrap a fresh Vite + React + TS app**

```
cd web && npm create vite@latest portal -- --template react-ts
cd portal && npm install react-router-dom && npm install -D tailwindcss postcss autoprefixer && npx tailwindcss init -p
```

- [ ] **Step 2: Strip Vite default boilerplate; mirror `web/client/` Tailwind config + base styles**

- [ ] **Step 3: Configure proxy in `web/portal/vite.config.ts`**

```ts
export default defineConfig({
  plugins: [react()],
  server: { port: 5274, proxy: { "/api": "http://localhost:8000" } },
});
```

- [ ] **Step 4: Add root npm scripts (`package.json` at repo root)**

```json
"scripts": {
  "dev:portal": "npm --prefix web/portal run dev",
  "build:portal": "npm --prefix web/portal run build"
}
```

- [ ] **Step 5: Boot the empty app**

Run: `npm run dev:portal`. Visit `http://localhost:5274/`. Empty page renders; commit baseline.

```
git commit -m "feat(portal): Vite scaffold for candidate portal"
```

---

## Task 10: `/apply` route (form + submit)

**Files:** `web/portal/src/routes/Apply.tsx`, `web/portal/src/lib/api.ts`

- [ ] **Step 1: Write the test**

```tsx
// tests/web/portal/Apply.test.tsx — uses @testing-library/react + msw
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { rest } from "msw";
import { setupServer } from "msw/node";
import Apply from "../../../web/portal/src/routes/Apply";

const server = setupServer(
  rest.post("/api/portal/apply", (req, res, ctx) =>
    res(ctx.status(202), ctx.json({ status: "submitted", candidate_id: "C-XYZ" })),
  ),
);
beforeAll(() => server.listen()); afterAll(() => server.close());

test("submits form and shows confirmation", async () => {
  render(<Apply />);
  fireEvent.change(screen.getByLabelText(/name/i), { target: { value: "Alice" } });
  fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "alice@example.com" } });
  fireEvent.change(screen.getByLabelText(/role/i), { target: { value: "REQ-SDE-USA-DEMO" } });
  const file = new File(["%PDF-1.4"], "cv.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText(/cv/i), { target: { files: [file] } });
  fireEvent.click(screen.getByRole("button", { name: /apply/i }));
  await waitFor(() => expect(screen.getByText(/submitted/i)).toBeInTheDocument());
});
```

- [ ] **Step 2: Implement `Apply.tsx`**

Form with: role dropdown (hard-coded options listed via `/api/portal/roles` later or static for now: `REQ-SDE-USA-DEMO`, `REQ-SDE-DE-DEMO`, `REQ-CD-USA-DEMO`), name, email, file input. On submit: `POST /api/portal/apply` as multipart/form-data, then render confirmation.

- [ ] **Step 3: Run tests; verify PASS**

- [ ] **Step 4: Commit**

---

## Task 11: `/portal?token=xxx` route

**Files:** `web/portal/src/routes/Portal.tsx`, `components/PhaseProgress.tsx`, `components/OfferPanel.tsx`, `components/OnboardingPanel.tsx`

- [ ] **Step 1: Test — phase morphs the surface**

```tsx
test("phase=offer shows accept/decline buttons", async () => {
  ...mock /api/portal/status to return phase: "offer", offer_letter_url: "..."
  expect(screen.getByRole("button", { name: /accept/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /decline/i })).toBeInTheDocument();
});

test("phase=onboarding shows video player", async () => {
  ...mock with phase: "onboarding", onboarding_video_url: "..."
  expect(screen.getByTestId("hg-video")).toHaveAttribute("src", "...");
});
```

- [ ] **Step 2: Implement**

```tsx
function Portal() {
  const token = new URLSearchParams(location.search).get("token")!;
  const { data } = useStatus(token);  // GET /api/portal/status/{token}
  if (!data) return <Loading/>;
  return (
    <div className="...">
      <PhaseProgress phase={data.phase}/>
      {data.phase === "screening" && <BookCallButton token={token}/>}
      {data.phase === "interview" && <InterviewRsvp ...details/>}
      {data.phase === "offer" && <OfferPanel token={token} url={data.offer_letter_url}/>}
      {data.phase === "onboarding" && <OnboardingPanel videoUrl={data.onboarding_video_url}/>}
    </div>
  );
}
```

- [ ] **Step 3: BookCallButton** redirects to `/screen?token=xxx` (the voice-real stream owns the route content; we just wire the link).

- [ ] **Step 4: OfferPanel** has Accept/Decline; on click `POST /api/portal/offer/{token}` with `?decision=accept|decline`. On 200 → re-fetch status.

- [ ] **Step 5: OnboardingPanel** renders `<video src={videoUrl} controls autoplay/>`.

- [ ] **Step 6: Tests pass; commit**

---

## Task 12: `/screen?token=xxx` placeholder

**Files:** `web/portal/src/routes/Screen.tsx`

- [ ] **Step 1: Stub** — full-screen layout with a `<div id="screen-call-mount"/>` placeholder. The voice-real stream's plan owns mounting the accelerator into this slot. Add a comment saying so.

- [ ] **Step 2: Commit**

```
git commit -m "feat(portal): /screen route placeholder for voice-real stream"
```

---

## Task 13: Admin Candidates panel (Control Plane fallback)

**Files:** `web/client/components/apex/CandidatesPanel.tsx`, route in `web/client/App.tsx`

- [ ] **Step 1: Add route `/candidates` to the admin Vite app's router**

- [ ] **Step 2: Component fetches `/api/portal/admin/links` (new admin route, IP-restrict-able later) and renders a table with copy-to-clipboard buttons per token**

- [ ] **Step 3: New backend route**

```python
@router.get("/admin/links")
async def admin_links():
    return {"links": app_state.magic_links.list_active()}
```

- [ ] **Step 4: Tests + commit**

```
git commit -m "feat(portal): admin Candidates panel — magic-link copy fallback"
```

---

## Task 14: Seed demo reqs (fixture)

**Files:** `data/synthetic/hiring/reqs.json` (NEW), loader update.

- [ ] **Step 1: Create a 3-req fixture**

```json
[
  {"id": "REQ-SDE-USA-DEMO", "title": "Senior Data Engineer", "jurisdiction": "USA"},
  {"id": "REQ-SDE-DE-DEMO",  "title": "Senior Data Engineer", "jurisdiction": "DE"},
  {"id": "REQ-CD-USA-DEMO",  "title": "Creative Director",    "jurisdiction": "USA"}
]
```

- [ ] **Step 2: Loader on FastAPI startup spawns three `HiringOrchestrator` instances seeded with these reqs (so apply has a workflow to attach to)**

- [ ] **Step 3: Commit**

---

## Acceptance criteria

- [ ] `npm run dev:portal` boots the portal at http://localhost:5274
- [ ] `/apply` form submits a PDF CV; backend returns `candidate_id`, the CV lands in Azurite Blob, and the workflow's Phase 4 Triage runs on the new CV
- [ ] On shortlist, an email with the magic link arrives in the ACS Email outbox AND appears in the admin Candidates panel
- [ ] `/portal?token=xxx` morphs by phase: shows progress bar always; Book Call button at Screening; RSVP at Interview; Accept/Decline at Offer; HeyGen video at Onboarding
- [ ] `/screen?token=xxx` renders the placeholder slot the voice-real stream will fill
- [ ] All tests under `tests/api/server/services/test_magic_link.py`, `test_email_send.py`, `test_blob_store.py`, `test_portal.py`, plus `tests/web/portal/*.test.tsx` are green

## Out of scope (per master spec)

- Hiring-manager-side req creation flow — reqs are fixture-seeded
- Payments / right-to-work doc upload
- Candidate-side chat / A2A surface
- Real auth beyond magic link (no SSO, no LinkedIn OAuth)
