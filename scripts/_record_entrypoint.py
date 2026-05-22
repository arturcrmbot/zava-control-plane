#!/usr/bin/env python
"""Record a replay tape for the public landing demo.

Runs an asyncio loop that:
  1. Constructs a Recorder.
  2. Starts it (snapshots state, subscribes to bus, sets active MutationBus).
  3. Sleeps forever (the substrate runs in this same process — cadence
     loops + simulator etc. are wired by importing app_state).
  4. On SIGINT / SIGTERM, calls Recorder.stop() to finalise the tarball.
  5. Enforces ``--min-seconds`` so an accidental Ctrl-C in the first few
     seconds yields no partial tape — the signal is logged and ignored
     until the minimum has elapsed.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
import time
from pathlib import Path
from typing import Callable


LogFn = Callable[[str], None]


def _print(message: str) -> None:
    print(message, flush=True)


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--min-seconds", type=int, default=0)
    return parser.parse_args(argv)


def _ignore_termination_signals() -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)


async def _wait_for_stop(
    *,
    stop_event: asyncio.Event,
    start_mono: float,
    min_seconds: int,
    log: LogFn,
) -> None:
    while True:
        await stop_event.wait()
        elapsed = time.monotonic() - start_mono
        if elapsed < min_seconds:
            remaining = min_seconds - elapsed
            log(f"[record] ignoring early signal — {remaining:.0f}s of min duration remain")
            stop_event.clear()
            continue
        return


async def main(argv: list[str]) -> int:
    args = _parse(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    from api.server.services.replay.recorder import Recorder
    from api.server.state import app_state

    recorder = Recorder(out_path=args.out, app_sha=os.environ.get("ZAVA_APP_SHA"))
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _on_signal(signame: str) -> None:
        _print(f"[record] received {signame}")
        stop_event.set()

    for signum, signame in ((signal.SIGINT, "SIGINT"), (signal.SIGTERM, "SIGTERM")):
        loop.add_signal_handler(signum, _on_signal, signame)

    await recorder.start()
    start_mono = time.monotonic()
    _print(f"[record] started → {args.out} (min_seconds={args.min_seconds})")

    try:
        await _wait_for_stop(
            stop_event=stop_event,
            start_mono=start_mono,
            min_seconds=args.min_seconds,
            log=_print,
        )
        _ignore_termination_signals()
        _print("[record] stopping…")
        out_path = await recorder.stop()
        _print(f"[record] wrote {out_path}")
        return 0
    finally:
        try:
            await app_state.aclose()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
