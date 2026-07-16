from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)


_REPO_ROOT = Path(__file__).resolve().parents[2]


def bootstrap(state) -> None:
    if not hasattr(state, "entities"):
        return
    state.entities.bootstrap_from_fixtures(
        employees_path=_REPO_ROOT / "data" / "synthetic" / "employees.json",
        vendors_path=_REPO_ROOT / "api" / "server" / "fixtures" / "vendors.json",
        agencies_path=_REPO_ROOT / "api" / "server" / "fixtures" / "agencies.json",
    )


async def start(state) -> tuple[Callable[[], Any], ...]:
    """Start Agency-only runtime services and return their stop actions."""
    from api.server.services import kpi_history
    from api.server.services.ambient_agents import (
        auto_block_rule_learner,
        brand_budget_watcher,
        kpi_history_recorder,
        story_pack_writer,
        subsidiary_capacity_watcher,
        trend_cadence_watcher,
        vendor_block_watcher,
    )
    from api.server.services.ambient_agents.talent_transfer_cascade import (
        TalentTransferCascade,
    )

    stops: list[Callable[[], Any]] = []

    try:
        await state.fm.start()
        stops.append(state.fm.stop)
    except Exception as exc:
        log.warning("Agency Fleet Manager failed to start: %s", exc)

    dispatcher = getattr(state, "ambient_dispatcher", None)
    if dispatcher is not None:
        try:
            dispatcher.start()
            stops.append(dispatcher.aclose)
        except Exception as exc:
            log.warning("Agency ambient dispatcher failed to start: %s", exc)

    def start_component(
        name: str,
        start_fn: Callable[[], Any],
        stop_fn: Callable[[], Any],
    ) -> None:
        try:
            start_fn()
            stops.append(stop_fn)
        except Exception as exc:
            log.warning("%s failed to start: %s", name, exc)

    entities = getattr(state, "entities", None)
    if entities is not None:
        start_component(
            "vendor_block_watcher",
            lambda: vendor_block_watcher.start(state.bus, entities),
            vendor_block_watcher.stop,
        )
        start_component(
            "brand_budget_watcher",
            lambda: brand_budget_watcher.start(state.bus, entities),
            brand_budget_watcher.stop,
        )

    start_component(
        "subsidiary_capacity_watcher",
        lambda: subsidiary_capacity_watcher.start(state.bus, state.store),
        subsidiary_capacity_watcher.stop,
    )
    start_component(
        "auto_block_rule_learner",
        lambda: auto_block_rule_learner.start(state.bus, entities),
        auto_block_rule_learner.stop,
    )
    start_component(
        "trend_cadence_watcher",
        lambda: trend_cadence_watcher.start(bus=state.bus),
        trend_cadence_watcher.stop,
    )
    start_component(
        "story_pack_writer",
        lambda: story_pack_writer.start(base_dir=state.data_dir / "snapshots"),
        story_pack_writer.stop,
    )

    try:
        kpi_history.set_db_path(state.data_dir / "kpi_history.sqlite")
        kpi_history_recorder.start()
        stops.append(kpi_history_recorder.stop)
    except Exception as exc:
        log.warning("kpi_history_recorder failed to start: %s", exc)

    try:
        cascade = TalentTransferCascade(
            bus=state.bus,
            audit=getattr(state, "audit", None),
            graph=entities,
        )
        cascade.start()
        state.talent_transfer_cascade = cascade
        stops.append(cascade.aclose)
    except Exception as exc:
        log.warning("TalentTransferCascade failed to start: %s", exc)

    return tuple(stops)


__all__ = ["bootstrap", "start"]
