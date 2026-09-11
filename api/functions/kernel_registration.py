from __future__ import annotations

import azure.durable_functions as df
import azure.functions as func

from api.shared.otel import init_otel


async def start_or_get_orchestration(
    client: df.DurableOrchestrationClient,
    *,
    function_name: str,
    payload: dict,
    requested_instance_id: str | None,
) -> tuple[str, bool, str | None]:
    if not requested_instance_id:
        return await client.start_new(function_name, None, payload), True, None

    existing = await client.get_status(requested_instance_id)
    # The Python SDK represents a missing instance as an empty status object.
    if getattr(existing, "runtime_status", None) is not None:
        runtime_status = getattr(existing, "runtime_status", None)
        runtime_status = getattr(runtime_status, "value", runtime_status)
        return requested_instance_id, False, (
            str(runtime_status) if runtime_status is not None else None
        )
    try:
        instance_id = await client.start_new(
            function_name,
            requested_instance_id,
            payload,
        )
        return instance_id, True, None
    except Exception:
        raced = await client.get_status(requested_instance_id)
        if getattr(raced, "runtime_status", None) is not None:
            runtime_status = getattr(raced, "runtime_status", None)
            runtime_status = getattr(runtime_status, "value", runtime_status)
            return requested_instance_id, False, (
                str(runtime_status) if runtime_status is not None else None
            )
        raise


def create_app() -> df.DFApp:
    init_otel("control-plane-functions")

    from api.server.services.governance import init_governance

    init_governance()
    app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)
    from api.functions.workflows.activities import checkpoint_activity

    @app.route(route="zava-ready", methods=["GET"])
    def runtime_ready(req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse('{"state":"Running"}', mimetype="application/json")

    @app.route(route="orchestrators/{functionName}")
    @app.durable_client_input(client_name="client")
    async def http_start(
        req: func.HttpRequest,
        client: df.DurableOrchestrationClient,
    ) -> func.HttpResponse:
        function_name = req.route_params.get("functionName")
        payload = req.get_json() if req.get_body() else {}
        requested_instance_id = (
            req.params.get("instance_id")
            or req.headers.get("x-orchestration-instance-id")
        )
        instance_id, started, runtime_status = await start_or_get_orchestration(
            client,
            function_name=function_name,
            payload=payload,
            requested_instance_id=requested_instance_id,
        )
        response = client.create_check_status_response(req, instance_id)
        response.headers["X-Zava-Orchestration-Started"] = (
            "true" if started else "false"
        )
        if runtime_status is not None:
            response.headers["X-Zava-Orchestration-Runtime-Status"] = runtime_status
        return response

    @app.activity_trigger(input_name="payload")
    def checkpoint_activity_trigger(payload: dict) -> dict:
        return checkpoint_activity(payload)

    return app
