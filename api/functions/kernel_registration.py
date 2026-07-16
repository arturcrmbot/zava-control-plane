from __future__ import annotations

import azure.durable_functions as df
import azure.functions as func

from api.shared.otel import init_otel


def create_app() -> df.DFApp:
    init_otel("control-plane-functions")

    from api.server.services.governance import init_governance

    init_governance()
    app = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)

    @app.route(route="orchestrators/{functionName}")
    @app.durable_client_input(client_name="client")
    async def http_start(
        req: func.HttpRequest,
        client: df.DurableOrchestrationClient,
    ) -> func.HttpResponse:
        function_name = req.route_params.get("functionName")
        payload = req.get_json() if req.get_body() else {}
        instance_id = await client.start_new(function_name, None, payload)
        return client.create_check_status_response(req, instance_id)

    return app
