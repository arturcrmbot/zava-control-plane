"""Pure projection of compose-domain brief YAML into UI composition data."""
from __future__ import annotations

import re
from typing import Any

import yaml


_LANES = {
    "deterministic": "automatic",
    "agent": "analysis",
    "hitl": "human",
}


def _collapse(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _humanize(value: Any) -> str:
    text = re.sub(r"[-_]+", " ", str(value or "")).strip()
    if not text:
        return ""
    return text[:1].upper() + text[1:].lower()


def _titleize(value: Any) -> str:
    return " ".join(part[:1].upper() + part[1:].lower()
                    for part in re.split(r"[-_\s]+", str(value or "").strip()) if part)


def _entity_component(entity: dict) -> dict:
    return {
        "type": "entity",
        "name": _humanize(entity.get("source")),
        "canonical": entity.get("kind"),
        "attributes": [
            {"k": key, "v": value}
            for key, value in (entity.get("attributes") or {}).items()
        ],
        "relations": [
            {"kind": rel.get("kind"), "target": rel.get("target_ref")}
            for rel in (entity.get("relations") or [])
        ],
    }


def _persona_component(persona: dict) -> dict:
    return {
        "type": "persona",
        "role": persona.get("role"),
        "name": _titleize(persona.get("role")),
        "decisionPolicy": _collapse(persona.get("decision_policy")),
    }


def _threshold(sentence: str) -> str | None:
    match = re.search(r"(?:GBP\s*|£)\s*([0-9][0-9,]*)", sentence)
    if not match:
        return None
    return f"GBP {match.group(1)}"


def _escalation_role(sentence: str) -> str | None:
    if not re.search(r"\b(sign-off|escalat\w*)\b", sentence, re.IGNORECASE):
        return None
    for match in re.finditer(r"\b([A-Z]{2,}|Board)\b", sentence):
        role = match.group(1)
        if role != "GBP":
            return role
    return None


def _authority_component(policy: str, persona_name: str) -> dict | None:
    for sentence in re.split(r"(?<=[.!?])\s+", policy):
        source = sentence.strip()
        threshold = _threshold(source)
        role = _escalation_role(source)
        if not threshold or not role:
            continue
        return {
            "type": "authority",
            "source": source,
            "threshold": threshold,
            "tiers": [
                {
                    "band": f"< {threshold}",
                    "approver": persona_name,
                    "cosign": None,
                    "escalatesIf": None,
                },
                {
                    "band": f"≥ {threshold}",
                    "approver": persona_name,
                    "cosign": role,
                    "escalatesIf": f"amount ≥ {threshold}",
                },
            ],
            "chain": [persona_name, role],
        }
    return None


def compose_summary(yaml_str: str) -> dict:
    """Project a compose-domain brief YAML string into a UI-shaped composition."""
    brief = yaml.safe_load(yaml_str) or {}
    domain = brief.get("domain") or {}
    phases = brief.get("phases") or []
    external_systems = {
        system.get("id"): system
        for system in (brief.get("external_systems") or [])
    }
    personae = {
        persona.get("role"): persona
        for persona in (brief.get("personae") or [])
    }
    entities = [_entity_component(entity) for entity in (brief.get("entities") or [])]

    steps = []
    for index, phase in enumerate(phases):
        kind = phase.get("kind")
        components = []
        if index == 0:
            components.extend(entities)
        if kind == "agent":
            components.append({
                "type": "skill",
                "name": phase.get("agent_skill_name"),
                "phase": phase.get("name"),
            })
            for system_id in (phase.get("external_systems") or []):
                system = external_systems.get(system_id) or {}
                components.append({
                    "type": "tool",
                    "name": system.get("mcp_tool"),
                    "system": system.get("id", system_id),
                    "operations": system.get("operations") or [],
                })
        if kind == "hitl":
            persona = personae.get(phase.get("persona")) or {"role": phase.get("persona")}
            persona_component = _persona_component(persona)
            components.append(persona_component)
            authority = _authority_component(
                persona_component["decisionPolicy"], persona_component["name"]
            )
            if authority:
                components.append(authority)

        steps.append({
            "id": phase.get("name"),
            "name": _humanize(phase.get("name")),
            "kind": kind,
            "lane": _LANES.get(kind, kind),
            "intent": _collapse(phase.get("intent")),
            "components": components,
        })

    ambient = brief.get("ambient") or {}
    triggers = ambient.get("triggers") or []
    all_components = [
        component
        for step in steps
        for component in step["components"]
    ]

    return {
        "title": domain.get("display_name"),
        "workflowType": domain.get("workflow_type"),
        "function": brief.get("function"),
        "steps": steps,
        "entities": entities,
        "ambient": {
            "name": ambient.get("name"),
            "trigger": (triggers[0] or {}).get("event_type") if triggers else None,
        },
        "counts": {
            "steps": len(steps),
            "personae": sum(1 for component in all_components if component["type"] == "persona"),
            "skills": sum(1 for component in all_components if component["type"] == "skill"),
            "tools": sum(1 for component in all_components if component["type"] == "tool"),
            "entities": len(entities),
            "rules": sum(
                len(component["tiers"])
                for component in all_components
                if component["type"] == "authority"
            ),
        },
    }
