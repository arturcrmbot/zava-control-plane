# Zava Public Story Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the aligned article and Constellation as one truthful public experience backed by a provenance-checked replay tape and automated GitHub Pages plus Azure Container Apps smoke tests.

**Architecture:** Retain the full `azure.yaml`/`deploy/Dockerfile` ACA path as the only dynamic public deployment. A local ignored manifest binds the replay tape to the clean source commit and passing proof. GitHub Pages receives the ACA URL at build time, ACA uses same-origin links, and Playwright verifies the deployed article, replay mode, Constellation orientation, and browser console.

**Tech Stack:** Python 3.13, Bash, TypeScript, Vitest, Playwright, GitHub Actions, Azure Developer CLI, Azure Container Apps

---

**Design authority:** `docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md`

**Depends on:**

- `docs/superpowers/plans/2026-08-10-zava-story-documentation-alignment.md`
- `docs/superpowers/plans/2026-08-10-blueprint-article-story-realignment.md`
- `docs/superpowers/plans/2026-08-10-constellation-guided-story.md`
- `docs/superpowers/plans/2026-08-10-zava-internal-skill-story-alignment.md`

**Owned files:**

- `tools/public_replay_manifest.py`
- `tests/tools/test_public_replay_manifest.py`
- `tests/tools/test_public_story_deployment.py`
- `web/blueprint/src/lib/useDemoUrl.ts`
- `web/blueprint/src/lib/__tests__/useDemoUrl.test.ts`
- `web/blueprint/vite.config.ts`
- `deploy/Dockerfile`
- `infra/main.parameters.json`
- `scripts/deploy-blueprint.sh`
- `.github/workflows/deploy-blueprint-pages.yml`
- `tests/e2e/public-story.spec.ts`
- Active references to `scripts/deploy-blueprint.sh`

**Local generated evidence, never committed:**

- `tapes/demo.tar.gz`
- `proof/manifest.json`
- `proof/public-replay.json`

**Out of scope:** Changing proof criteria, automatically approving seller review, weakening tenant isolation, adding live public write access, or editing article and HUD copy owned by earlier plans.

### Task 1: Bind the ignored replay tape to source and proof

**Files:**
- Create: `tools/public_replay_manifest.py`
- Create: `tests/tools/test_public_replay_manifest.py`

- [ ] **Step 1: Write failing manifest tests**

```python
import io
import json
import tarfile
from pathlib import Path

import pytest

from tools.public_replay_manifest import build_manifest, verify_manifest


def _write_tape(path: Path) -> None:
    meta = json.dumps(
        {
            "tape_id": "tape_test",
            "recorded_at": "2026-08-10T09:00:00+00:00",
            "duration_s": 60,
            "version": 1,
            "app_sha": "abc1234",
        },
    ).encode()
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo("./meta.json")
        info.size = len(meta)
        archive.addfile(info, io.BytesIO(meta))


def _write_proof(path: Path, source_commit: str) -> None:
    path.write_text(
        json.dumps(
            {
                "source_commit": source_commit,
                "live_result": "PASS",
                "replay_result": "PASS",
                "seller_review": "PENDING",
                "browserErrors": [],
            },
        ),
    )


def _write_seller_review(path: Path, status: str = "PASS") -> None:
    path.write_text(
        json.dumps(
            {
                "status": status,
                "owner": "operator",
                "machine_may_approve": False,
                "questions": [
                    {"id": 1, "question": "Story coherent?", "answer": True},
                ],
            },
        ),
    )


def test_build_manifest_binds_tape_proof_and_story(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)

    manifest = build_manifest(tape, proof, seller_review, "a" * 40)

    assert manifest["source_commit"] == "a" * 40
    assert len(manifest["tape_sha256"]) == 64
    assert len(manifest["proof_manifest_sha256"]) == 64
    assert len(manifest["seller_review_sha256"]) == 64
    assert manifest["recorded_at"] == "2026-08-10T09:00:00+00:00"
    assert manifest["story_contract"].endswith(
        "2026-08-10-zava-constellation-story-design.md",
    )


def test_build_manifest_refuses_pending_seller_review(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review, status="PENDING")

    with pytest.raises(ValueError, match="seller_review must be PASS"):
        build_manifest(tape, proof, seller_review, "a" * 40)


def test_verify_manifest_detects_tape_drift(tmp_path: Path) -> None:
    tape = tmp_path / "demo.tar.gz"
    proof = tmp_path / "manifest.json"
    seller_review = tmp_path / "seller-review.json"
    manifest_path = tmp_path / "public-replay.json"
    _write_tape(tape)
    _write_proof(proof, "a" * 40)
    _write_seller_review(seller_review)
    manifest_path.write_text(
        json.dumps(build_manifest(tape, proof, seller_review, "a" * 40)),
    )

    with tape.open("ab") as stream:
        stream.write(b"drift")

    with pytest.raises(ValueError, match="tape sha256 mismatch"):
        verify_manifest(tape, proof, seller_review, manifest_path, "a" * 40)
```

- [ ] **Step 2: Run the tests and verify they fail**

```bash
uv run pytest tests/tools/test_public_replay_manifest.py -q
```

Expected: collection error because `tools.public_replay_manifest` does not exist.

- [ ] **Step 3: Implement the manifest tool**

```python
from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any


STORY_CONTRACT = (
    "docs/superpowers/specs/"
    "2026-08-10-zava-constellation-story-design.md"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tape_meta(path: Path) -> dict[str, Any]:
    with tarfile.open(path, "r:gz") as archive:
        member = archive.getmember("./meta.json")
        stream = archive.extractfile(member)
        if stream is None:
            raise ValueError("tape meta.json is unreadable")
        return json.loads(stream.read())


def _proof(path: Path, source_commit: str) -> dict[str, Any]:
    proof = json.loads(path.read_text(encoding="utf-8"))
    if proof.get("source_commit") != source_commit:
        raise ValueError("proof source_commit does not match HEAD")
    if proof.get("live_result") != "PASS":
        raise ValueError("live_result must be PASS")
    if proof.get("replay_result") != "PASS":
        raise ValueError("replay_result must be PASS")
    if proof.get("browserErrors") != []:
        raise ValueError("browserErrors must be empty")
    return proof


def _seller_review(path: Path) -> dict[str, Any]:
    review = json.loads(path.read_text(encoding="utf-8"))
    if review.get("machine_may_approve") is not False:
        raise ValueError("seller review must remain operator-owned")
    if review.get("status") != "PASS":
        raise ValueError("seller_review must be PASS")
    questions = review.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("seller review questions are required")
    if any(item.get("answer") in (None, False, "") for item in questions):
        raise ValueError("all seller review questions must pass")
    return review


def build_manifest(
    tape_path: Path,
    proof_path: Path,
    seller_review_path: Path,
    source_commit: str,
) -> dict[str, Any]:
    _proof(proof_path, source_commit)
    _seller_review(seller_review_path)
    meta = _tape_meta(tape_path)
    return {
        "schema_version": 1,
        "source_commit": source_commit,
        "story_contract": STORY_CONTRACT,
        "tape_id": meta["tape_id"],
        "recorded_at": meta["recorded_at"],
        "tape_sha256": _sha256(tape_path),
        "proof_manifest_sha256": _sha256(proof_path),
        "seller_review_sha256": _sha256(seller_review_path),
    }


def verify_manifest(
    tape_path: Path,
    proof_path: Path,
    seller_review_path: Path,
    manifest_path: Path,
    source_commit: str,
) -> None:
    expected = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual = build_manifest(
        tape_path,
        proof_path,
        seller_review_path,
        source_commit,
    )
    if expected["source_commit"] != actual["source_commit"]:
        raise ValueError("source_commit mismatch")
    if expected["tape_sha256"] != actual["tape_sha256"]:
        raise ValueError("tape sha256 mismatch")
    if expected["proof_manifest_sha256"] != actual["proof_manifest_sha256"]:
        raise ValueError("proof manifest sha256 mismatch")
    if expected["seller_review_sha256"] != actual["seller_review_sha256"]:
        raise ValueError("seller review sha256 mismatch")
    if expected["story_contract"] != STORY_CONTRACT:
        raise ValueError("story contract mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("write", "verify"))
    parser.add_argument("--tape", type=Path, default=Path("tapes/demo.tar.gz"))
    parser.add_argument("--proof", type=Path, default=Path("proof/manifest.json"))
    parser.add_argument(
        "--seller-review",
        type=Path,
        default=Path("proof/seller-review.json"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("proof/public-replay.json"),
    )
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()

    if args.command == "write":
        payload = build_manifest(
            args.tape,
            args.proof,
            args.seller_review,
            args.source_commit,
        )
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        verify_manifest(
            args.tape,
            args.proof,
            args.seller_review,
            args.manifest,
            args.source_commit,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run manifest tests**

```bash
uv run pytest tests/tools/test_public_replay_manifest.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit manifest tooling**

```bash
git add tools/public_replay_manifest.py \
  tests/tools/test_public_replay_manifest.py
git commit -m "feat(deploy): bind public replay evidence"
```

### Task 2: Remove the hardcoded ACA URL

**Files:**
- Modify: `web/blueprint/src/lib/useDemoUrl.ts`
- Create: `web/blueprint/src/lib/__tests__/useDemoUrl.test.ts`
- Modify: `web/blueprint/vite.config.ts`
- Modify: `deploy/Dockerfile:35-37`

- [ ] **Step 1: Write pure URL-builder tests**

```typescript
import { describe, expect, it } from "vitest";
import { buildDemoUrl } from "../useDemoUrl";

describe("buildDemoUrl", () => {
  it("adds source attribution without losing existing query parameters", () => {
    expect(
      buildDemoUrl("https://example.test/?mode=replay", "observatory"),
    ).toBe("https://example.test/?mode=replay&from=observatory");
  });

  it("normalises a base without a trailing slash", () => {
    expect(buildDemoUrl("https://example.test", "closing")).toBe(
      "https://example.test/?from=closing",
    );
  });
});
```

- [ ] **Step 2: Run the test and verify it fails**

```bash
npm exec vitest -- run \
  web/blueprint/src/lib/__tests__/useDemoUrl.test.ts
```

Expected: FAIL because `buildDemoUrl` does not exist.

- [ ] **Step 3: Replace the hardcoded fallback with build-time or same-origin resolution**

```typescript
function localDemoBase(): string {
  if (typeof window === "undefined") return "/";
  const { protocol, hostname, port, origin } = window.location;
  if (port === "5275") return `${protocol}//${hostname}:5273/`;
  return `${origin}/`;
}

export function buildDemoUrl(
  base: string,
  source: string,
  origin: string = window.location.origin,
): string {
  const url = new URL(base, origin);
  url.searchParams.set("from", source);
  return url.toString();
}

export function getDemoUrl(source: string = "essay"): string {
  const configured = (
    (import.meta as unknown as {
      env?: { VITE_DEMO_URL?: string };
    }).env?.VITE_DEMO_URL ?? ""
  ).trim();
  return buildDemoUrl(configured || localDemoBase(), source);
}
```

No Azure hostname remains in source.

- [ ] **Step 4: Fail non-root builds without an explicit demo URL**

In `web/blueprint/vite.config.ts`, after calculating `base`:

```typescript
if (base !== "/" && !process.env.VITE_DEMO_URL) {
  throw new Error(
    "VITE_DEMO_URL is required when building the blueprint below a path prefix",
  );
}
```

In `deploy/Dockerfile`, build the same-origin ACA bundle with:

```dockerfile
RUN npm --prefix web/blueprint install --no-audit --no-fund \
    && BASE_PATH=/blueprint/ VITE_DEMO_URL=/ npm --prefix web/blueprint run build
```

- [ ] **Step 5: Run URL tests and builds**

```bash
npm exec vitest -- run \
  web/blueprint/src/lib/__tests__/useDemoUrl.test.ts
VITE_DEMO_URL=https://example.test/ npm run build:blueprint
```

Expected: PASS.

- [ ] **Step 6: Commit URL configuration**

```bash
git add web/blueprint/src/lib/useDemoUrl.ts \
  web/blueprint/src/lib/__tests__/useDemoUrl.test.ts \
  web/blueprint/vite.config.ts deploy/Dockerfile
git commit -m "fix(deploy): configure public replay URL"
```

### Task 3: Replace the broken static ACA script with the proof-gated full deploy

**Files:**
- Modify: `infra/main.parameters.json:19`
- Modify: `scripts/deploy-blueprint.sh`
- Create: `tests/tools/test_public_story_deployment.py`
- Modify active references to `scripts/deploy-blueprint.sh`

- [ ] **Step 1: Write deployment contract tests**

```python
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_azd_requires_an_explicit_mode() -> None:
    params = json.loads((ROOT / "infra/main.parameters.json").read_text())
    assert params["parameters"]["zavaMode"]["value"] == "${ZAVA_MODE}"


def test_public_deploy_uses_the_full_azd_path() -> None:
    script = (ROOT / "scripts/deploy-blueprint.sh").read_text()
    assert '[[ "${ZAVA_MODE:-}" == "replay" ]]' in script
    assert "proof/public-replay.json" in script
    assert "EXPECTED_TENANT_ID" in script
    assert "python tools/public_replay_manifest.py verify" in script
    assert "azd up" in script
    assert "/api/replay/meta" in script
    assert "web/blueprint/Dockerfile" not in script
    assert "az acr create" not in script


def test_active_docs_do_not_describe_the_old_static_aca_path() -> None:
    active = [
        ROOT / "README.md",
        ROOT / "docs/DEVELOPMENT.md",
        ROOT / "docs/blueprint-microsite-contributor-guide.md",
        ROOT / "docs/superpowers/skills/compose-domain/SKILL.md",
        ROOT / "docs/superpowers/skills/compose-domain/templates/GRADUATION.md.tmpl",
    ]
    for path in active:
        text = path.read_text()
        assert "nginx-only blueprint ACA" not in text
        assert "zava-workspace-deploy" in text or "azd" in text
```

- [ ] **Step 2: Run the contract and verify it fails**

```bash
uv run pytest tests/tools/test_public_story_deployment.py -q
```

Expected: FAIL because mode defaults to live and the script builds the
nginx-only blueprint image.

- [ ] **Step 3: Require explicit deployment mode**

Change:

```json
"zavaMode": { "value": "${ZAVA_MODE=live}" }
```

to:

```json
"zavaMode": { "value": "${ZAVA_MODE}" }
```

- [ ] **Step 4: Replace `scripts/deploy-blueprint.sh`**

```bash
#!/usr/bin/env bash
# Deploy the public Zava experience as a proof-gated ACA replay.
set -euo pipefail

cd "$(dirname "$0")/.."

for command in az azd git jq python curl; do
  command -v "$command" >/dev/null || {
    echo "Missing required command: $command" >&2
    exit 2
  }
done

[[ "${ZAVA_MODE:-}" == "replay" ]] || {
  echo "Set ZAVA_MODE=replay for the public deployment." >&2
  exit 2
}
[[ -n "${EXPECTED_TENANT_ID:-}" ]] || {
  echo "EXPECTED_TENANT_ID is required." >&2
  exit 2
}
[[ -f proof/public-replay.json ]] || {
  echo "Run the public replay manifest write step first." >&2
  exit 2
}

HEAD_SHA="$(git rev-parse HEAD)"
python tools/public_replay_manifest.py verify \
  --source-commit "$HEAD_SHA" \
  --tape tapes/demo.tar.gz \
  --proof proof/manifest.json \
  --seller-review proof/seller-review.json \
  --manifest proof/public-replay.json

ACTUAL_TENANT_ID="$(az account show --query tenantId -o tsv)"
[[ "$ACTUAL_TENANT_ID" == "$EXPECTED_TENANT_ID" ]] || {
  echo "Tenant mismatch: expected $EXPECTED_TENANT_ID, got $ACTUAL_TENANT_ID" >&2
  exit 2
}

azd up

FQDN="$(azd env get-value AZURE_CONTAINER_APP_FQDN)"
curl -fsS "https://${FQDN}/healthz" >/dev/null
curl -fsS "https://${FQDN}/api/replay/meta" |
  jq -e '.mode == "replay" and (.recorded_at | type == "string")' >/dev/null
curl -fsS "https://${FQDN}/api/blueprint/composition" |
  jq -e '.domains | length > 0' >/dev/null

printf 'Public replay deployed and verified: https://%s/\n' "$FQDN"
```

- [ ] **Step 5: Update active references**

Keep `scripts/deploy-blueprint.sh` as the command, but replace descriptions of a
blueprint-only static ACA with:

```markdown
`scripts/deploy-blueprint.sh` is the proof-gated wrapper around the canonical
`azure.yaml` deployment. It requires `ZAVA_MODE=replay`, tenant verification,
`proof/manifest.json`, and `proof/public-replay.json`; it deploys the full
read-only replay application, not an nginx-only microsite.
```

Apply that description in:

- `README.md`;
- `docs/DEVELOPMENT.md`;
- `docs/blueprint-microsite-contributor-guide.md`;
- `docs/superpowers/skills/compose-domain/SKILL.md`;
- `docs/superpowers/skills/compose-domain/templates/GRADUATION.md.tmpl`.

- [ ] **Step 6: Run deployment contract tests**

```bash
uv run pytest tests/tools/test_public_story_deployment.py -q
```

Expected: PASS.

- [ ] **Step 7: Check shell syntax and commit**

```bash
bash -n scripts/deploy-blueprint.sh
git add infra/main.parameters.json scripts/deploy-blueprint.sh \
  tests/tools/test_public_story_deployment.py README.md docs/DEVELOPMENT.md \
  docs/blueprint-microsite-contributor-guide.md \
  docs/superpowers/skills/compose-domain/SKILL.md \
  docs/superpowers/skills/compose-domain/templates/GRADUATION.md.tmpl
git commit -m "fix(deploy): use proof-gated ACA replay"
```

### Task 4: Add deployed article and Constellation smoke tests

**Files:**
- Create: `tests/e2e/public-story.spec.ts`
- Modify: `.github/workflows/deploy-blueprint-pages.yml`

- [ ] **Step 1: Write the public story Playwright test**

```typescript
import { expect, test, type Page } from "@playwright/test";

const pagesUrl = process.env.PUBLIC_STORY_URL;
const replayUrl = process.env.ACA_REPLAY_URL;

function required(value: string | undefined, name: string): string {
  if (!value) throw new Error(`${name} is required`);
  return value.replace(/\/$/, "");
}

function captureErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(String(error)));
  return errors;
}

test("published article carries the approved promise and ACA link", async ({
  page,
}) => {
  const story = required(pagesUrl, "PUBLIC_STORY_URL");
  const replay = required(replayUrl, "ACA_REPLAY_URL");
  const errors = captureErrors(page);

  await page.goto(story, { waitUntil: "networkidle" });
  await expect(
    page.getByText(/See what an agentic organisation actually looks like/i),
  ).toBeVisible();
  const link = page.getByRole("link", { name: /Open Constellation/i });
  await expect(link).toHaveAttribute("href", new RegExp(`^${replay}`));
  expect(errors).toEqual([]);
});

test("ACA is a truthful replay and Constellation explains itself", async ({
  page,
  request,
}) => {
  const replay = required(replayUrl, "ACA_REPLAY_URL");
  const meta = await request.get(`${replay}/api/replay/meta`);
  expect(meta.ok()).toBeTruthy();
  expect(await meta.json()).toMatchObject({ mode: "replay" });

  const errors = captureErrors(page);
  await page.goto(`${replay}/blueprint/?view=constellation`, {
    waitUntil: "domcontentloaded",
  });
  await expect(
    page.getByText(/watching a working agentic organisation/i),
  ).toBeVisible();
  await expect(page.getByText(/Recorded telemetry/i)).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Follow one decision/i }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
```

- [ ] **Step 2: Run against a local replay stack**

```bash
ZAVA_MODE=replay ZAVA_TAPE_PATH=tapes/demo.tar.gz scripts/boot-demo.sh &
BOOT_PID=$!
trap 'kill "$BOOT_PID" 2>/dev/null || true' EXIT
sleep 15
PUBLIC_STORY_URL=http://127.0.0.1:5275 \
ACA_REPLAY_URL=http://127.0.0.1:3101 \
  npx playwright test tests/e2e/public-story.spec.ts
```

Expected: PASS after the earlier article and Constellation plans are implemented.

- [ ] **Step 3: Inject the replay URL into the Pages build**

In the `vite build` step:

```yaml
env:
  BASE_PATH: /${{ github.event.repository.name }}/
  VITE_DEMO_URL: ${{ vars.ACA_REPLAY_URL }}
```

Add the story spec path to the workflow trigger:

```yaml
- "docs/superpowers/specs/2026-08-10-zava-constellation-story-design.md"
```

- [ ] **Step 4: Expose the deployed Pages URL**

Add to the `deploy` job:

```yaml
outputs:
  page_url: ${{ steps.deployment.outputs.page_url }}
```

- [ ] **Step 5: Add a post-deploy verification job**

```yaml
verify:
  name: verify public story
  needs: deploy
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: "20"
        cache: "npm"
    - run: npm ci
    - run: npx playwright install --with-deps chromium
    - name: Verify article and replay
      env:
        PUBLIC_STORY_URL: ${{ needs.deploy.outputs.page_url }}
        ACA_REPLAY_URL: ${{ vars.ACA_REPLAY_URL }}
      run: npx playwright test tests/e2e/public-story.spec.ts
```

- [ ] **Step 6: Commit deployment verification**

```bash
git add tests/e2e/public-story.spec.ts \
  .github/workflows/deploy-blueprint-pages.yml
git commit -m "test(deploy): verify public Zava story"
```

### Task 5: Produce and publish the canonical replay

**Files:**
- Generate locally: `tapes/demo.tar.gz`
- Generate locally: `proof/manifest.json`
- Generate locally: `proof/public-replay.json`
- No source-file edits expected.

- [ ] **Step 1: Start from a clean committed source**

```bash
git status --short
git rev-parse HEAD
```

Expected: clean working tree and one stable source SHA.

- [ ] **Step 2: Run the relevant complete vertical/public proof**

Use the proof command selected by the active pack, for example:

```bash
make prove VERTICAL=telco
```

Verify the machine-owned result:

```bash
jq -e --arg head "$(git rev-parse HEAD)" '
  .source_commit == $head and
  .live_result == "PASS" and
  .replay_result == "PASS" and
  .seller_review == "PENDING" and
  .browserErrors == []
' proof/manifest.json
```

Expected: exits successfully.

- [ ] **Step 3: Record the organisation-wide public tape**

```bash
DURATION=2h OUT=tapes/demo.tar.gz scripts/record_tape.sh
```

Expected: `tapes/demo.tar.gz` exists and contains `events.ndjson`,
`meta.json`, and `snapshot_t0/`.

- [ ] **Step 4: Perform the human seller review**

Review the article and local replay together:

```bash
ZAVA_MODE=replay ZAVA_TAPE_PATH=tapes/demo.tar.gz scripts/boot-demo.sh
```

The reviewer verifies:

- the 30-second explanation centres the agentic organisation;
- Constellation shows organisation-wide activity and the Aurora journey;
- real, synthetic, and customer connection boundaries are visible;
- no browser errors occur;
- no surface implies a mandatory simulation-first adoption path.

Only the human reviewer changes `proof/seller-review.json`. Keep
`proof/manifest.json` machine-owned with `seller_review: "PENDING"`:

```json
{
  "status": "PASS",
  "owner": "operator",
  "machine_may_approve": false,
  "questions": [
    {
      "id": 1,
      "question": "Is the industry and operating setting recognisable?",
      "answer": true
    },
    {
      "id": 2,
      "question": "Is the business event understandable without narration?",
      "answer": true
    },
    {
      "id": 3,
      "question": "Is it visible why the process started?",
      "answer": true
    },
    {
      "id": 4,
      "question": "Are the agent and human decisions inspectable?",
      "answer": true
    },
    {
      "id": 5,
      "question": "Is the business and Knowledge-graph outcome visible?",
      "answer": true
    }
  ]
}
```

Machine tooling must not make that change.

- [ ] **Step 5: Write and verify public replay provenance**

```bash
HEAD_SHA="$(git rev-parse HEAD)"
python tools/public_replay_manifest.py write \
  --source-commit "$HEAD_SHA" \
  --tape tapes/demo.tar.gz \
  --proof proof/manifest.json \
  --seller-review proof/seller-review.json \
  --manifest proof/public-replay.json
python tools/public_replay_manifest.py verify \
  --source-commit "$HEAD_SHA" \
  --tape tapes/demo.tar.gz \
  --proof proof/manifest.json \
  --seller-review proof/seller-review.json \
  --manifest proof/public-replay.json
```

Expected: both commands exit successfully.

- [ ] **Step 6: Deploy through tenant-isolated public replay**

```bash
export ZAVA_MODE=replay
test -n "${EXPECTED_TENANT_ID:?azure-tenant-isolation must set EXPECTED_TENANT_ID}"
./scripts/deploy-blueprint.sh
```

Expected: the script validates proof and provenance, verifies the tenant, runs
`azd up`, and prints the healthy ACA replay URL.

- [ ] **Step 7: Set the GitHub repository variable and deploy Pages**

Set the repository variable from the deployed azd environment, then run the
`deploy-blueprint-pages` workflow:

```bash
ACA_REPLAY_URL="https://$(azd env get-value AZURE_CONTAINER_APP_FQDN)"
gh variable set ACA_REPLAY_URL --body "$ACA_REPLAY_URL"
gh workflow run deploy-blueprint-pages.yml
```

- [ ] **Step 8: Confirm the workflow verification job passes**

Expected: `build`, `deploy`, and `verify public story` all PASS.

### Task 6: Final deployment regression

**Files:**
- Verify only; no changes expected.

- [ ] **Step 1: Run targeted unit and contract tests**

```bash
uv run pytest \
  tests/tools/test_public_replay_manifest.py \
  tests/tools/test_public_story_deployment.py -q
npm exec vitest -- run \
  web/blueprint/src/lib/__tests__/useDemoUrl.test.ts
```

Expected: PASS.

- [ ] **Step 2: Run the public story smoke against deployed URLs**

```bash
ACA_REPLAY_URL="https://$(azd env get-value AZURE_CONTAINER_APP_FQDN)"
PUBLIC_STORY_URL="https://arturcrmbot.github.io/zava-control-plane/" \
ACA_REPLAY_URL="$ACA_REPLAY_URL" \
  npx playwright test tests/e2e/public-story.spec.ts
```

Expected: PASS with zero browser console errors.
