from __future__ import annotations

import os

_MODE_ENV = "ZAVA_MODE"
_REPLAY_VALUE = "replay"
_TAPE_PATH_ENV = "ZAVA_TAPE_PATH"


def is_replay() -> bool:
    """True when the process should boot in replay-only mode."""
    return os.environ.get(_MODE_ENV, "").strip().lower() == _REPLAY_VALUE


def tape_path() -> str | None:
    """Path to the tape archive — required when is_replay() is True."""
    p = os.environ.get(_TAPE_PATH_ENV, "").strip()
    return p or None
