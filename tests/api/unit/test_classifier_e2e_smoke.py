"""End-to-end smoke: 5 real classifier calls, assert schema validity only.

Run: ./.venv/Scripts/pytest.exe tests/api/unit/test_classifier_e2e_smoke.py -m smoke -v
Skipped by default — requires `gh auth` and live model calls."""
from __future__ import annotations
import pytest

from api.functions.graphs.executors.agents import agent_rag_classifier
from api.functions.graphs.executors.validators import validate_classification_schema as schema

pytestmark = pytest.mark.smoke

CLAIM_IDS = ["CLM-0000", "CLM-0007", "CLM-0009", "CLM-0014", "CLM-0019"]


@pytest.mark.parametrize("claim_id", CLAIM_IDS)
async def test_real_classifier_returns_valid_payload(claim_id):
    result = await agent_rag_classifier.execute({"claim_id": claim_id})
    payload = result["classification"]
    schema.validate(payload)
    assert payload["verdict"] in {"green", "amber", "red"}
