"""Hourly "story of the morning" pack (pitch-j5).

Renders a short markdown summary of what the substrate did in a given
time window — top events, biggest entity-graph deltas, learning-loop
wins. Surfaced in the cosmic-lens HUD via
``GET /api/story-pack/latest`` and on disk under ``data/snapshots/``
so a presenter can pop one open mid-demo.

Pure functions plus one stateless writer; the hourly cadence lives in
``api.server.services.ambient_agents.story_pack_writer``.
"""
from __future__ import annotations

import datetime as _dt
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger(__name__)


# Event-type → source track label used in the "learning wins" section.
_LEARNING_EVENT_LABELS: dict[str, str] = {
    "policy.installed":      "I2 auto-block rule installed",
    "classifier.cache_hit":  "I3 classifier cache hit",
    "routing.rebalanced":    "I4 routing rebalance",
    "trend.fired":           "I5 trend-driven cadence",
}


def _safe_audit_entries() -> list[dict]:
    """Pull the in-memory audit ledger; return ``[]`` on any failure.

    Late-imported so this module can be loaded by unit tests that don't
    construct the full :class:`AppState` (the import side-effect builds
    a kuzu graph + http clients).
    """
    try:
        from api.server.state import app_state
    except Exception:
        return []
    audit = getattr(app_state, "audit", None)
    if audit is None:
        return []
    try:
        return list(audit.list())
    except Exception:
        log.exception("story_pack: audit.list() failed")
        return []


def _entry_ts(entry: dict) -> float | None:
    ts = entry.get("timestamp")
    if isinstance(ts, (int, float)):
        return float(ts)
    return None


def _filter_window(
    entries: Iterable[dict],
    *,
    since_unix_ts: float,
    until_unix_ts: float | None,
) -> list[dict]:
    out: list[dict] = []
    upper = until_unix_ts if until_unix_ts is not None else float("inf")
    for e in entries:
        ts = _entry_ts(e)
        if ts is None:
            continue
        if since_unix_ts <= ts < upper:
            out.append(e)
    return out


def _format_iso(ts: float) -> str:
    return _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _top_events(entries: list[dict], n: int = 10) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for e in entries:
        action = e.get("action")
        if isinstance(action, str) and action:
            counter[action] += 1
    return counter.most_common(n)


def _entity_deltas(entries: list[dict]) -> list[tuple[str, int]]:
    """Count entity-graph mutations per ``kind``.

    Pulls from ``entity.upserted`` and ``entity.linked`` actions which
    both carry a ``kind`` (or ``rel`` for links) on their ``details``.
    Returns the top 10 in descending order.
    """
    counter: Counter[str] = Counter()
    for e in entries:
        action = e.get("action")
        details = e.get("details") or {}
        if not isinstance(details, dict):
            continue
        if action == "entity.upserted":
            kind = details.get("kind")
            if isinstance(kind, str) and kind:
                counter[f"upsert {kind}"] += 1
        elif action == "entity.linked":
            rel = details.get("rel")
            if isinstance(rel, str) and rel:
                counter[f"link {rel}"] += 1
    return counter.most_common(10)


def _learning_wins(entries: list[dict]) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for e in entries:
        action = e.get("action")
        label = _LEARNING_EVENT_LABELS.get(action) if isinstance(action, str) else None
        if label is None:
            continue
        counter[label] += 1
    # Stable order: by count desc, then label.
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


def _format_md(
    *,
    since_unix_ts: float,
    until_unix_ts: float | None,
    entries: list[dict],
    top: list[tuple[str, int]],
    deltas: list[tuple[str, int]],
    wins: list[tuple[str, int]],
) -> str:
    until_str = (
        _format_iso(until_unix_ts) if until_unix_ts is not None else "now"
    )
    lines: list[str] = []
    lines.append(f"# Story of the hour")
    lines.append("")
    lines.append(
        f"Window: `{_format_iso(since_unix_ts)}` → `{until_str}` "
        f"({len(entries)} audit entries)"
    )
    lines.append("")
    lines.append("## Top 10 events")
    if top:
        for action, count in top:
            lines.append(f"- **{action}** — {count}")
    else:
        lines.append("- _no events recorded in window_")
    lines.append("")
    lines.append("## Biggest entity-graph deltas")
    if deltas:
        for kind, count in deltas:
            lines.append(f"- {kind}: {count}")
    else:
        lines.append("- _no entity mutations in window_")
    lines.append("")
    lines.append("## Learning-loop wins")
    if wins:
        for label, count in wins:
            lines.append(f"- {label}: {count}")
    else:
        lines.append("- _no learning events in window_")
    lines.append("")
    return "\n".join(lines)


def render_story(
    *, since_unix_ts: float, until_unix_ts: float | None = None
) -> str:
    """Markdown summary of the time window.

    Pulls from :class:`AuditLogger`, counts the biggest entity-graph
    deltas (per kind) and lists learning events (auto-block installs,
    routing rebalances, classifier cache hits, trend triggers). The
    returned string is ready to write to disk.
    """
    entries = _safe_audit_entries()
    windowed = _filter_window(
        entries,
        since_unix_ts=since_unix_ts,
        until_unix_ts=until_unix_ts,
    )
    top = _top_events(windowed)
    deltas = _entity_deltas(windowed)
    wins = _learning_wins(windowed)
    return _format_md(
        since_unix_ts=since_unix_ts,
        until_unix_ts=until_unix_ts,
        entries=windowed,
        top=top,
        deltas=deltas,
        wins=wins,
    )


def _hour_floor(ts: float) -> _dt.datetime:
    """Floor ``ts`` to the hour, in UTC."""
    return _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc).replace(
        minute=0, second=0, microsecond=0
    )


def _story_filename(hour_start: _dt.datetime) -> str:
    """Stable per-hour filename. The (hour, hour+1) window is the key."""
    return f"story-{hour_start.strftime('%Y-%m-%dT%H')}.md"


def write_hourly_story(
    *, base_dir: Path | str = Path("data/snapshots"), now_ts: float | None = None
) -> Path:
    """Render + write the most recent hour's story to ``base_dir``.

    Returns the path written. Idempotent on the (hour, hour+1) key —
    if the file already exists for that hour, it is overwritten in
    place rather than duplicated. ``now_ts`` is injectable for tests.
    """
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    if now_ts is None:
        now_ts = _dt.datetime.now(tz=_dt.timezone.utc).timestamp()
    # Most recent COMPLETED hour: floor(now) - 1h ... floor(now).
    current_hour = _hour_floor(now_ts)
    hour_start = current_hour - _dt.timedelta(hours=1)
    hour_end = current_hour

    md = render_story(
        since_unix_ts=hour_start.timestamp(),
        until_unix_ts=hour_end.timestamp(),
    )
    path = base_dir / _story_filename(hour_start)
    path.write_text(md, encoding="utf-8")
    return path
