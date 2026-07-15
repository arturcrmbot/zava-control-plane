from __future__ import annotations

from typing import Any

import pytest

from api.server.services import simulator_orchestrator


async def _noop_wait_for_functions_host(*_args: Any, **_kwargs: Any) -> None:
    return None


@pytest.mark.asyncio
async def test_ramp_loop_defaults_to_non_world_owned_live_domains_when_vertical_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIMULATOR_RAMP_ENABLED", "1")
    monkeypatch.delenv("SIMULATOR_RAMP_DOMAINS", raising=False)
    monkeypatch.delenv("ZAVA_VERTICAL", raising=False)
    monkeypatch.setattr(simulator_orchestrator, "_wait_for_functions_host", _noop_wait_for_functions_host)

    scheduled: list[str] = []

    async def fake_per_domain_ramp(
        domain: str,
        spawn_fn,
        avg_interval: float,
        initial_delay: float = 0.0,
        scenario_rotation: list[str] | None = None,
    ) -> None:
        scheduled.append(domain)

    monkeypatch.setattr(simulator_orchestrator, "_per_domain_ramp", fake_per_domain_ramp)
    monkeypatch.setattr(simulator_orchestrator, "_resolve_spawner", lambda domain: domain.workflow_type)
    monkeypatch.setattr(simulator_orchestrator, "_effective_interval", lambda domain: 1.0)
    monkeypatch.setattr(simulator_orchestrator, "_scenarios_for", lambda _workflow_type: None)

    await simulator_orchestrator.ramp_loop()

    assert scheduled == [
        domain.workflow_type
        for domain in simulator_orchestrator.live_domains()
        if domain.workflow_type not in simulator_orchestrator._WORLD_OWNED_RAMP_TYPES
        and domain.spawn_fn
    ]


@pytest.mark.asyncio
async def test_ramp_loop_uses_profile_ramp_domains_when_csv_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.shared.verticals import VerticalProfile

    monkeypatch.setenv("SIMULATOR_RAMP_ENABLED", "1")
    monkeypatch.delenv("SIMULATOR_RAMP_DOMAINS", raising=False)
    monkeypatch.setattr(simulator_orchestrator, "_wait_for_functions_host", _noop_wait_for_functions_host)
    monkeypatch.setattr(
        simulator_orchestrator,
        "active_vertical",
        lambda: VerticalProfile(
            name="demo",
            world="toy",
            workflow_types=("expense-claim",),
            ramp_workflow_types=("expense-claim",),
        ),
    )

    scheduled: list[str] = []

    async def fake_per_domain_ramp(
        domain: str,
        spawn_fn,
        avg_interval: float,
        initial_delay: float = 0.0,
        scenario_rotation: list[str] | None = None,
    ) -> None:
        scheduled.append(domain)

    monkeypatch.setattr(simulator_orchestrator, "_per_domain_ramp", fake_per_domain_ramp)
    monkeypatch.setattr(simulator_orchestrator, "_resolve_spawner", lambda domain: domain.workflow_type)
    monkeypatch.setattr(simulator_orchestrator, "_effective_interval", lambda domain: 1.0)
    monkeypatch.setattr(simulator_orchestrator, "_scenarios_for", lambda _workflow_type: None)

    await simulator_orchestrator.ramp_loop()

    assert scheduled == ["expense-claim"]


@pytest.mark.asyncio
async def test_ramp_loop_explicit_csv_cannot_spawn_world_owned_domains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIMULATOR_RAMP_ENABLED", "1")
    monkeypatch.setenv("ZAVA_VERTICAL", "telco")
    monkeypatch.setenv("SIMULATOR_RAMP_DOMAINS", "expense-claim,network-incident")
    monkeypatch.setattr(simulator_orchestrator, "_wait_for_functions_host", _noop_wait_for_functions_host)

    scheduled: list[str] = []

    async def fake_per_domain_ramp(
        domain: str,
        spawn_fn,
        avg_interval: float,
        initial_delay: float = 0.0,
        scenario_rotation: list[str] | None = None,
    ) -> None:
        scheduled.append(domain)

    monkeypatch.setattr(simulator_orchestrator, "_per_domain_ramp", fake_per_domain_ramp)
    monkeypatch.setattr(simulator_orchestrator, "_resolve_spawner", lambda domain: domain.workflow_type)
    monkeypatch.setattr(simulator_orchestrator, "_effective_interval", lambda domain: 1.0)
    monkeypatch.setattr(simulator_orchestrator, "_scenarios_for", lambda _workflow_type: None)

    await simulator_orchestrator.ramp_loop()

    assert scheduled == ["expense-claim"]


@pytest.mark.asyncio
async def test_ramp_loop_has_no_telco_timer_noise_when_profile_ramp_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIMULATOR_RAMP_ENABLED", "1")
    monkeypatch.setenv("ZAVA_VERTICAL", "telco")
    monkeypatch.delenv("SIMULATOR_RAMP_DOMAINS", raising=False)
    monkeypatch.setattr(simulator_orchestrator, "_wait_for_functions_host", _noop_wait_for_functions_host)

    scheduled: list[str] = []

    async def fake_per_domain_ramp(
        domain: str,
        spawn_fn,
        avg_interval: float,
        initial_delay: float = 0.0,
        scenario_rotation: list[str] | None = None,
    ) -> None:
        scheduled.append(domain)

    monkeypatch.setattr(simulator_orchestrator, "_per_domain_ramp", fake_per_domain_ramp)
    monkeypatch.setattr(simulator_orchestrator, "_resolve_spawner", lambda domain: domain.workflow_type)
    monkeypatch.setattr(simulator_orchestrator, "_effective_interval", lambda domain: 1.0)
    monkeypatch.setattr(simulator_orchestrator, "_scenarios_for", lambda _workflow_type: None)

    await simulator_orchestrator.ramp_loop()

    assert scheduled == []
