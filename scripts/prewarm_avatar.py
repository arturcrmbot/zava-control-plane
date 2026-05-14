"""Pre-render demo onboarding videos so the cache is warm before the demo.

Loads `data/synthetic/hiring/onboarding_scripts.json` and calls
`avatar_render` for each entry. Cache hits are no-ops; cache misses render
via Azure AI Speech batch synthesis (2-3 min wall-clock each), upload to
Blob, and persist the cache row.

Usage:
    uv run python scripts/prewarm_avatar.py
    uv run python scripts/prewarm_avatar.py path/to/custom.json

Env vars required:
    AZURE_SPEECH_REGION                 (e.g. eastus)
    AZURE_STORAGE_CONNECTION_STRING     (Azurite or real Storage account)
    Plus Entra ID auth for Cognitive Services Speech User role on the
    Speech resource (DefaultAzureCredential).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from api.server.mcp_tools.avatar_render import avatar_render, is_configured


_DEFAULT_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "synthetic"
    / "hiring"
    / "onboarding_scripts.json"
)


def main(argv: list[str]) -> int:
    fixture_path = Path(argv[1]) if len(argv) > 1 else _DEFAULT_FIXTURE
    if not fixture_path.exists():
        print(f"[prewarm] fixture not found: {fixture_path}", file=sys.stderr)
        return 2

    if not is_configured():
        print(
            "[prewarm] avatar_render not configured. Set AZURE_SPEECH_REGION + "
            "AZURE_STORAGE_CONNECTION_STRING (and unset AVATAR_TRANSPORT=mock).",
            file=sys.stderr,
        )
        return 3

    entries = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        print(f"[prewarm] fixture must be a JSON array, got {type(entries)}", file=sys.stderr)
        return 2

    rendered = 0
    cached = 0
    failed = 0
    for i, entry in enumerate(entries, start=1):
        role = entry.get("role", "?")
        script = entry.get("script", "")
        avatar_character = entry.get("avatar_character", "lisa")
        avatar_style = entry.get("avatar_style", "graceful-sitting")
        voice = entry.get("voice", "en-US-JennyNeural")
        if not script:
            print(f"[prewarm] [{i}/{len(entries)}] {role}: empty script, skipping")
            continue
        print(
            f"[prewarm] [{i}/{len(entries)}] role={role!r} avatar={avatar_character} "
            f"style={avatar_style} voice={voice}"
        )
        result = avatar_render(
            script=script,
            avatar_character=avatar_character,
            avatar_style=avatar_style,
            voice=voice,
        )
        if result.result_type != "success":
            print(f"  -> FAILED: {result.error}")
            failed += 1
            continue
        if result.cached:
            print(f"  -> cached (hit): {result.video_url}")
            cached += 1
        else:
            print(f"  -> rendered: {result.video_url}")
            rendered += 1

    print(
        f"[prewarm] done. rendered={rendered} cached={cached} failed={failed} "
        f"total={len(entries)}"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
