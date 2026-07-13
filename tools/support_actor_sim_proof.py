"""Run and prove the explicit-actor support simulation without FastAPI/Durable."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from api.server.world.packs.support import DemandSurge, SupportConfig, run_support
from api.server.world.projection import project_support


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("tmp/support-actor-proof"))
    args = parser.parse_args()

    config = SupportConfig(
        customer_count=1_000,
        worker_count=40,
        arrival_rate_per_hour=90,
        simulation_minutes=480,
        sla_minutes=30,
        sensor_backlog_threshold=25,
        sensor_recovery_threshold=10,
    )
    surges = (DemandSurge(at_minute=120, multiplier=4, duration_minutes=90),)
    first = run_support(seed=args.seed, config=config, surges=surges)
    replay = run_support(seed=args.seed, config=config, surges=surges)
    deterministic = first.runtime.canonical_journal() == replay.runtime.canonical_journal()
    if not deterministic:
        raise SystemExit("FAIL: identical seed/input produced a different journal")

    args.output.mkdir(parents=True, exist_ok=True)
    journal_path = first.runtime.export_ndjson(args.output / "journal.ndjson")
    projection = project_support(first)
    summary = {
        "seed": args.seed,
        "deterministic_replay": deterministic,
        "customers": len(first.customers),
        "workers": len(first.workers),
        "tickets": len(first.tickets),
        "events": len(first.runtime.journal),
        "sensor_episodes": sum(
            event.type == "sensor.tripped" for event in first.runtime.journal
        ),
        "projection": {
            field: getattr(projection, field)
            for field in projection.__dataclass_fields__
        },
        "journal": str(journal_path),
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
