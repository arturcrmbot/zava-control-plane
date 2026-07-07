import json
from pathlib import Path

from api.server.services.compose.brief_model import compose_summary


ROOT = Path(__file__).resolve().parents[3]
BRIEF = ROOT / "docs/superpowers/specs/capex-approval-brief.yaml"
FIXTURE = ROOT / "tests/api/compose/fixtures/capex_composition.json"


def test_compose_summary_matches_capex_fixture():
    assert compose_summary(BRIEF.read_text()) == json.loads(FIXTURE.read_text())


def test_compose_summary_humanizes_phase_name():
    yaml = """
domain:
  workflow_type: sample
  display_name: Sample
function: finance
phases:
  - name: budget_check
    kind: deterministic
    intent: Check budget.
ambient:
  name: Watcher
  triggers:
    - event_type: sample.created
"""

    result = compose_summary(yaml)

    assert result["steps"][0]["name"] == "Budget check"


def test_compose_summary_omits_authority_without_threshold():
    yaml = """
domain:
  workflow_type: sample
  display_name: Sample
function: finance
phases:
  - name: approval
    kind: hitl
    intent: Approve or reject.
    persona: finance_controller
personae:
  - role: finance_controller
    decision_policy: Approve normal requests and escalate unusual risks.
ambient:
  name: Watcher
  triggers:
    - event_type: sample.created
"""

    result = compose_summary(yaml)

    assert result["steps"][0]["components"] == [
        {
            "type": "persona",
            "role": "finance_controller",
            "name": "Finance Controller",
            "decisionPolicy": "Approve normal requests and escalate unusual risks.",
        }
    ]
    assert result["counts"]["rules"] == 0


def test_compose_summary_counts_components():
    result = compose_summary(BRIEF.read_text())

    assert result["counts"] == {
        "steps": 4,
        "personae": 1,
        "skills": 1,
        "tools": 1,
        "entities": 4,
        "rules": 2,
    }
