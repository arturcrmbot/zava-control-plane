from __future__ import annotations

import pytest
import json


def test_functions_worker_exposes_internal_readiness():
    from api.functions.kernel_registration import create_app

    app = create_app()
    function = next(
        (item for item in app.get_functions() if item.get_function_name() == "runtime_ready"),
        None,
    )
    assert function is not None
    bindings = json.loads(function.get_function_json())["bindings"]
    trigger = next(binding for binding in bindings if binding["type"] == "httpTrigger")
    assert trigger["route"] == "zava-ready"
    response = function.get_user_function()(None)
    assert response.status_code == 200
    assert json.loads(response.get_body()) == {"state": "Running"}


class _Client:
    def __init__(self, status):
        self.status = status
        self.started = []

    async def get_status(self, instance_id):
        return self.status

    async def start_new(self, function_name, instance_id, payload):
        self.started.append((function_name, instance_id, payload))
        return instance_id or "random-instance"


@pytest.mark.asyncio
async def test_explicit_instance_starts_only_when_durable_has_no_history():
    from api.functions.kernel_registration import start_or_get_orchestration

    client = _Client(None)
    instance_id, started, runtime_status = await start_or_get_orchestration(
        client,
        function_name="AuroraBudgetResponseOrchestrator",
        payload={"workflow_id": "AUR-1"},
        requested_instance_id="aurora-request-1",
    )

    assert instance_id == "aurora-request-1"
    assert started is True
    assert runtime_status is None
    assert client.started == [(
        "AuroraBudgetResponseOrchestrator",
        "aurora-request-1",
        {"workflow_id": "AUR-1"},
    )]


@pytest.mark.asyncio
async def test_empty_sdk_status_is_not_an_existing_orchestration():
    from azure.durable_functions.models.DurableOrchestrationStatus import DurableOrchestrationStatus
    from api.functions.kernel_registration import start_or_get_orchestration

    client = _Client(DurableOrchestrationStatus.from_json({}))
    instance_id, started, status = await start_or_get_orchestration(
        client,
        function_name="AuroraBudgetResponseOrchestrator",
        payload={"workflow_id": "AUR-1"},
        requested_instance_id="aurora-request-1",
    )

    assert (instance_id, started, status) == ("aurora-request-1", True, None)
    assert len(client.started) == 1


@pytest.mark.asyncio
async def test_start_failure_is_not_hidden_by_an_empty_sdk_status():
    from azure.durable_functions.models.DurableOrchestrationStatus import DurableOrchestrationStatus
    from api.functions.kernel_registration import start_or_get_orchestration

    class FailingClient(_Client):
        async def start_new(self, *args):
            raise RuntimeError("Storage unavailable")

    client = FailingClient(DurableOrchestrationStatus.from_json({}))
    with pytest.raises(RuntimeError, match="Storage unavailable"):
        await start_or_get_orchestration(
            client,
            function_name="AuroraBudgetResponseOrchestrator",
            payload={"workflow_id": "AUR-1"},
            requested_instance_id="aurora-request-1",
        )


@pytest.mark.asyncio
async def test_explicit_instance_returns_existing_terminal_history_without_restart():
    from api.functions.kernel_registration import start_or_get_orchestration

    client = _Client(type("Status", (), {"runtime_status": "Completed"})())
    instance_id, started, runtime_status = await start_or_get_orchestration(
        client,
        function_name="AuroraBudgetResponseOrchestrator",
        payload={"workflow_id": "AUR-1"},
        requested_instance_id="aurora-request-1",
    )

    assert instance_id == "aurora-request-1"
    assert started is False
    assert runtime_status == "Completed"
    assert client.started == []


@pytest.mark.asyncio
async def test_default_starter_preserves_random_instance_behavior():
    from api.functions.kernel_registration import start_or_get_orchestration

    client = _Client(None)
    instance_id, started, runtime_status = await start_or_get_orchestration(
        client,
        function_name="ExpenseClaimOrchestrator",
        payload={"workflow_id": "EXP-1"},
        requested_instance_id=None,
    )

    assert instance_id == "random-instance"
    assert started is True
    assert runtime_status is None
    assert client.started == [(
        "ExpenseClaimOrchestrator",
        None,
        {"workflow_id": "EXP-1"},
    )]
