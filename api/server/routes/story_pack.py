"""Story-pack read endpoints (pitch-j5).

Surfaces the most recent hourly markdown stories written to disk by
:mod:`api.server.services.ambient_agents.story_pack_writer` so the
HUD can render a "what happened" panel without each browser session
re-rendering the audit ledger.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Query

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/story-pack")

def _list_story_files(base_dir: Path) -> list[Path]:
    """Return story-*.md files sorted newest-first.

    Sort uses the embedded ISO hour stamp (lexicographic == chronological)
    so we don't depend on filesystem mtime which can drift across a
    move / restore.
    """
    if not base_dir.exists():
        return []
    files = [p for p in base_dir.glob("story-*.md") if p.is_file()]
    files.sort(key=lambda p: p.name, reverse=True)
    return files


@router.get("/latest")
def latest(
    n: int = Query(5, ge=1, le=50),
    base_dir: str | None = Query(None, include_in_schema=False),
) -> dict:
    """Return the ``n`` most recent story packs.

    Each item: ``{"hour": "<YYYY-MM-DDTHH>", "markdown": "..."}``.
    Reverse-chronological. Empty list when no stories have been
    written yet (cold demo, ambient writer hasn't ticked).
    """
    if base_dir:
        root = Path(base_dir)
    else:
        from api.server.services.story_pack import default_base_dir

        root = default_base_dir()
    items: list[dict] = []
    for p in _list_story_files(root)[:n]:
        # filename: story-<YYYY-MM-DDTHH>.md
        hour = p.stem[len("story-"):] if p.stem.startswith("story-") else p.stem
        try:
            md = p.read_text(encoding="utf-8")
        except Exception:
            log.exception("story_pack: failed reading %s", p)
            continue
        items.append({"hour": hour, "markdown": md})
    return {"items": items}
