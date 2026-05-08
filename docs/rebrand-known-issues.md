# Rebrand WPP → Zava — known issues

Tracked binary artefacts where the literal token `WPP` may appear inside
binary payloads. Per CON-003 of [`plan/refactor-rebrand-zava-1.md`](../plan/refactor-rebrand-zava-1.md),
these are NOT regenerated in this rebrand — logged here as known cosmetic risks.

## KNOWN-ISSUE-WPP-PIXEL-LEAK — welcome-video MP4 files

Captured 2026-05-08 via `rg -l '\bWPP\b' data/portal/welcome-videos --binary`.
13 files matched. Likely false positives — the byte sequence `WPP` appearing
inside H.264 / AAC compressed payload, not visible video text. None of these
videos visibly say "WPP" on screen (verified previously during Phase 5 demo
recordings).

If a stray pixel turns up later: rerun `python scripts/prewarm_avatar.py`
which re-renders these via HeyGen. Out of scope for this rebrand pass.

- data/portal/welcome-videos/alex-doe.mp4
- data/portal/welcome-videos/alex-park.mp4
- data/portal/welcome-videos/and-ahdi.mp4
- data/portal/welcome-videos/anya-hoffmann.mp4
- data/portal/welcome-videos/daniel-chen.mp4
- data/portal/welcome-videos/felix-becker.mp4
- data/portal/welcome-videos/isabel-k-nig.mp4
- data/portal/welcome-videos/jordan-lee.mp4
- data/portal/welcome-videos/lara-schmidt.mp4
- data/portal/welcome-videos/maria-rivera.mp4
- data/portal/welcome-videos/priya-mehta.mp4
- data/portal/welcome-videos/richard-james.mp4
- data/portal/welcome-videos/tobias-klein.mp4

## Resolved binary artefacts

- **Receipt PNGs** (`data/synthetic/receipts/*.png`): zero binary matches.
  No action.
- **CV PDFs** (`data/synthetic/hiring/cv-pdfs/*.pdf`): 50 files leaked stale
  `author="WPP Talent"` metadata. **Resolved 2026-05-08** by regenerating via
  `python scripts/generate_cv_pdfs.py` after Phase 4 rebranded the script's
  `author=` argument. Final binary scan: zero matches.
