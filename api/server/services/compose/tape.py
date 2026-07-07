"""Compose tapes: record/replay the normalized event stream of a compose run.

Format mirrors data/blueprint-recordings/: one JSONL file per run, each line
{"ts_offset_ms": int, "event": <normalized compose event>}.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from api.shared.compose_config import repo_root


def _dir() -> Path:
    d = repo_root() / "data" / "compose-recordings"
    return d


def save_tape(session, workflow_type: str) -> Path:
    d = _dir()
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    safe = (workflow_type or "compose").replace("/", "-")
    path = d / f"{safe}-{stamp}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for entry in session.timeline:
            fh.write(json.dumps(entry) + "\n")
    return path


def list_tapes() -> list[str]:
    d = _dir()
    if not d.exists():
        return []
    return sorted(p.name for p in d.glob("*.jsonl"))


def load_tape(name: str) -> list[dict]:
    path = _dir() / Path(name).name  # prevent traversal
    with path.open(encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]
