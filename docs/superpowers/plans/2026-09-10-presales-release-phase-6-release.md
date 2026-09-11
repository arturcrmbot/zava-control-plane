# Presales Release Proof and Handoff Implementation Plan

> **For agentic workers:** Use `executing-plans` after implementation approval. Follow the [master plan](2026-09-10-presales-release-readiness.md). Provisioning, paid calls, human sign-off and publication are separate permissions.

**Goal:** Publish one source-bound, approved reference package that another Microsoft colleague can deploy and present.

**Architecture:** Reuse existing proof tools and publishing wrappers. Freeze source before capture, bind immutable build inputs explicitly, and keep public replay separate from private-live validation. Preserve the previous public release until the new one is approved.

**Tech Stack:** Existing Docker/azd pipeline, pytest, Vitest, Playwright, replay recorder and proof manifests.

**Status:** Superseded by [master plan v2](2026-09-10-presales-release-readiness.md). Reference only; existing proof and human publication gates remain mandatory, but the old six-phase programme is not.

---

## Task 6.1: Extend the existing proof path for Agency

**Files**

- Create: `tools/agency_zava_e2e_proof.py`
- Create: `tools/agency_zava_e2e_proof.sh`
- Create: `tests/tools/test_agency_zava_e2e_proof.py`
- Reuse: `tools/workflow_visibility_proof.py`
- Reuse: `tools/public_replay_manifest.py`
- Modify: `Makefile`
- Modify: `docs/VERTICAL-PROOF.md` only for directly required generic contract clarification

- [ ] Implement a thin Agency orchestration of existing checks, not another proof framework. `make prove VERTICAL=agency` must invoke the same existing proof/visibility contracts.
- [ ] Require actual Functions management-state evidence for root/children, not merely control-plane timeline rows. Match runtime instance IDs with workflow/detail/AG-UI identities.
- [ ] Capture approve, reject, timeout, missing Functions, denied authority, provider failure, duplicate start, duplicate decision, API restart and full-container replacement.
- [ ] Compare the same workflow IDs in live and replay using the existing visibility checker, including exact tool request/response/status/duration and recorded decision provenance.
- [ ] Run installed-pack inventory/registration regressions for all seven packs. Collect distinct evidence for every workflow claimed in the selected Agency release. Existing gaps block an "entire pack ready" claim; do not hide them by rewriting maturity flags.
- [ ] Keep proof payloads in ignored `proof/` or the approved artifact store. Public artifacts contain only reviewed synthetic records, never secrets or private customer material.

**Commands added by the earlier phases**

```bash
make test-presales-runtime
make test-aurora
make test-harness
make prove VERTICAL=agency
```

The first three are offline checks. The proof command requires an explicitly selected running test environment and permission for any live model use; it must not discover and reset the user's normal environment.

## Task 6.2: Freeze, build and capture without a provenance loop

**Files**

- Modify: `scripts/build-blueprint-image.sh`
- Modify: `tools/public_replay_manifest.py`
- Modify: `tests/tools/test_public_replay_manifest.py`
- Modify: `deploy/Dockerfile` only for explicit immutable artifact inputs
- Modify: `docs/DEVELOPMENT.md`

- [ ] Freeze reviewed application source as `RELEASE_SOURCE_COMMIT` after commit approval. Require a clean source tree and record dependency locks. If code changes during proof, freeze a new source commit and repeat affected live/replay evidence.
- [ ] Build a native target-platform image and run the real live proof from that source. Generate the tape and workflow-detail export from that run.
- [ ] Package recordings/media as separately hashed build inputs, not source files edited after the provenance check. The release image must identify application SHA and each artifact hash. Do not rewrite tape `app_sha` to match a later asset-only commit.
- [ ] Record both the live-proof image digest and final replay-image digest. Re-exercise the final replay image; a boot overlay or intermediate image is not evidence for the published image.
- [ ] Keep film/site provenance explicit if their editorial publication commit differs from application source. Every depicted execution remains bound to its actual source/run; do not claim all assets came from one SHA when they did not.
- [ ] Extend `build_manifest`/`verify_manifest` rather than adding a second authoritative release manifest. Include the Phase 4 journey/detail hashes and approved media manifest.

**Acceptance:** source, tape, evidence, images and public assets form a verifiable chain. Recording output cannot silently dirty source and then be relabelled as the source just tested.

## Task 6.3: Complete live and replay operational gates

**Files**

- Extend: `tools/agency_zava_e2e_proof.py`
- Modify: `tests/e2e/public-story.spec.ts`
- Modify: `docs/DEVELOPMENT.md`
- Record: ignored release evidence under `proof/`

- [ ] Run private-live from a clean approved reference environment, with no developer `gh` login when Azure is selected. Confirm real provider/tool work and authenticated operator authority.
- [ ] Replace the API/container while CFO approval is pending. Reopen the page and resolve that same gate. Verify no missing workflow, duplicate policy write or duplicate child execution.
- [ ] Break required persistence, provider and Functions dependencies one at a time. Readiness must fail without converting missing work into successful outcomes.
- [ ] Keep a browser mounted through backend restart/reconnection. No manual reload is needed to recover current state; stale cursors are detected.
- [ ] Run a **normal-speed** replay soak for at least 150 minutes, beyond the previous 131-minute failure window. Also cover at least three complete recording loops. An accelerated test cannot replace this requirement.
- [ ] Record working-set memory after warmup and at regular intervals. Require no unbounded per-loop growth, no OOM/restart, no live graph writes/governance decisions and no dropped terminal evidence. Bound expected cache warmup separately rather than declaring any small increase a leak.
- [ ] Exercise the actual final image's article, operator UI, portal navigation and Constellation deep links. Run the public-story test against the staging release with source/hash comparisons, not only static label assertions.

## Task 6.4: Obtain human approval and publish

**Files**

- Use: `scripts/deploy-blueprint.sh`
- Use: Phase 3's private-live wrapper and runbook
- Update: `README.md`
- Update: `docs/DEVELOPMENT.md`
- Update: `docs/blueprint-microsite-contributor-guide.md`
- Record: `proof/seller-review.json` through the existing operator-owned process

- [ ] Ask the human reviewer to assess reset, pacing, business meaning, visible authority, readability, film/audio and consistency of claims. Leave approval pending until that person completes it.
- [ ] Have a colleague follow the reference installation and seller guide without backstage fixes from the author. Include one failure/recovery exercise and one question about what is synthetic.
- [ ] Request approval for the exact tenant/subscription/mode and public release. Run the existing provenance/tenant-gated publishing path; do not call a lower-level deploy command to bypass it.
- [ ] After publication, compare public metadata, source, fingerprint, journey IDs and asset hashes with the approved manifest. Derive README recording date/duration from that metadata; remove stale hand-maintained descriptions.
- [ ] Preserve the previous approved public replay for rollback. Document the exact prior image/artifact reference without deleting it.
- [ ] Update the master plan and phase checkboxes only for completed work. Record unresolved non-release issues separately rather than calling the technology "100% correct".

## Final acceptance

The release is complete only when:

1. The Agency/Aurora story runs through real governed parent/child execution.
2. A private Azure reference survives the declared restart/idempotency cases.
3. Public replay is current, read-only and bound to its actual evidence.
4. Article, guide, film and seller/builder kit describe the same supported scope.
5. Human seller review and publication approval are genuine.
6. A colleague can deploy and present the reference using the supplied instructions.

If any item fails, report its exact state and leave publication blocked. The fallback is the prior approved read-only release, not weaker controls or invented proof.
