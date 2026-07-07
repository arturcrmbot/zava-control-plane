"""Real compose smoke test. NOT run in CI — spawns a real `copilot` agent and
mutates the tree. Enable with COMPOSE_E2E=1 on a throwaway checkout.

Run: COMPOSE_E2E=1 uv run pytest tests/api/compose/test_integration_real.py -v -s
"""
import os
import asyncio
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("COMPOSE_E2E") != "1", reason="set COMPOSE_E2E=1 to run real agent")


@pytest.mark.asyncio
async def test_real_compose_reaches_brief_stage():
    from api.server.services.compose import registry
    from api.server.services.compose.session import ComposeSession
    from api.server.services.compose.bridge import ComposeBridge

    registry.reset()
    session = ComposeSession("e2e")
    registry.register(session)
    doc = ("Capital expenditure approval: staff raise a capex request; finance "
           "checks budget; senior leaders approve above a threshold; assets are "
           "recorded. Approvers above 50k are ambiguous.")
    bridge = ComposeBridge(session, document_text=doc)  # real copilot bin
    await bridge.start()

    q = session.subscribe()
    saw_brief = False
    for _ in range(400):
        ev = await asyncio.wait_for(q.get(), timeout=900)
        if ev.get("type") == "question":
            session.resolve(ev["request_id"], "Create a new capex_committee persona")
        if ev.get("type") == "brief":
            saw_brief = True
            session.resolve(ev["request_id"], {"approved": True, "yaml": ev["yaml"]})
        if ev.get("type") == "done" or (ev.get("type") == "stage" and ev.get("stage") in ("ready", "error")):
            break
    assert saw_brief, "agent never presented a brief"
