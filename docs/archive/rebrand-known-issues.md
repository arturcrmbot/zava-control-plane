# Rebrand legacy-brand → Zava — known issues

Tracked binary artefacts where a legacy brand token may appear inside
binary payloads. Per CON-003 of [`plan/refactor-rebrand-zava-1.md`](../../plan/refactor-rebrand-zava-1.md),
these are NOT regenerated in this rebrand — logged here as known cosmetic risks.

## KNOWN-ISSUE-LEGACY-PIXEL-LEAK — welcome-video MP4 files

Captured 2026-05-08 via a binary scan under `data/portal/welcome-videos`.
13 files matched. Likely false positives — a legacy byte sequence appearing
inside H.264 / AAC compressed payload, not visible video text. None of these
videos visibly show old-brand text on screen (verified previously during Phase 5 demo
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

## KNOWN-ISSUE-LEGACY-PIXEL-LEAK — hex-ID candidate PDFs (601 files)

`data/synthetic/hiring/cv-pdfs/C-XXXXXXXX.pdf` (601 files with 8-hex-char IDs)
carry stale `/Author (...)` metadata from a one-time generator that no
longer ships in the repo. Their JSON sources are not present (only the 50
named CVs `C-WE-USA-XX` etc. have JSON in `data/synthetic/hiring/cvs/`).

Visible PDF body content is unaffected (the hex-ID PDFs use the same
template body, only the metadata header carries the stale author string).

To resolve: either run the upstream generator (lost from repo) or strip
PDF metadata in-place via `pikepdf` / `pdftk update_info`. Deferred to a
follow-up plan; not blocking the rebrand demo path since `/Author` only
shows in PDF reader properties dialogs, not in the `apply` route or
cv-crystalliser OCR.

## Resolved binary artefacts

- **Receipt PNGs** (`data/synthetic/receipts/*.png`): zero binary matches.
  No action.
- **CV PDFs (named, 50 files)** `data/synthetic/hiring/cv-pdfs/C-WE-USA-XX.pdf`
  etc.: leaked stale author metadata. **Resolved 2026-05-08**
  by regenerating via `python scripts/generate_cv_pdfs.py` after Phase 4
  rebranded the script's `author=` argument. Final binary scan: zero matches
  on the named subset.
