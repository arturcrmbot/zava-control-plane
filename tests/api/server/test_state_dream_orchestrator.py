"""AppState exposes a memoised dream-pass orchestrator and domain memories."""

import os

os.environ.setdefault("ENTITY_PLANE_ENABLED", "0")

from api.server.services.dream_pass.orchestrator import DreamPassOrchestrator


def test_app_state_exposes_dream_pass_orchestrator():
    from api.server.state import app_state
    assert isinstance(app_state.dream_pass_orchestrator, DreamPassOrchestrator)


def test_app_state_exposes_domain_memories_mapping():
    from api.server.state import app_state
    assert isinstance(app_state.domain_memories, dict)


def test_dream_pass_orchestrator_is_memoised():
    from api.server.state import app_state
    assert app_state.dream_pass_orchestrator is app_state.dream_pass_orchestrator
