from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from api.server.state import app_state
from api.shared.functions import FUNCTIONS, PersonaTree
from api.shared import personas as personas_registry


def _persona_tree_to_dict(node: PersonaTree) -> dict[str, Any]:
    return {
        "role": node.role,
        "manages": [_persona_tree_to_dict(child) for child in node.manages],
    }


def _snapshot_workflows() -> list[dict[str, Any]]:
    store = getattr(app_state, "store", None)
    if store is None or not hasattr(store, "list_workflows"):
        return []
    return [
        workflow.model_dump(by_alias=True, mode="json")
        for workflow in store.list_workflows()
    ]


def _snapshot_exceptions() -> list[dict[str, Any]]:
    store = getattr(app_state, "store", None)
    if store is None or not hasattr(store, "list_exceptions"):
        return []
    return [
        exception.model_dump(by_alias=True, mode="json")
        for exception in store.list_exceptions()
    ]


def _load_personae_definitions() -> dict[str, Any]:
    from api.server.services import persona_responder

    definitions = persona_responder.PERSONA_DEFINITIONS
    if definitions:
        return definitions
    return persona_responder._load_personae()


def _snapshot_personae() -> dict[str, Any]:
    definitions = _load_personae_definitions()
    items: list[dict[str, Any]] = []
    for role, definition in sorted(definitions.items()):
        registered = personas_registry.get(role)
        item = asdict(registered) if registered is not None else {
            "role": definition.role,
            "archetype": "",
            "scope_function": "",
            "workflow_label": definition.workflow_label,
            "external_event_default": definition.external_event,
            "scope_business_unit": "*",
            "scope_geography": "*",
            "default_authority_band": None,
            "uses_authority_mcp": False,
            "description": definition.description,
            "display_color": None,
        }
        item.update(
            {
                "role": definition.role,
                "workflow_label": definition.workflow_label,
                "external_event_default": definition.external_event,
                "description": definition.description,
            }
        )
        items.append(item)

    by_archetype = Counter(
        item["archetype"] for item in items if item.get("archetype")
    )
    by_function = Counter(
        item["scope_function"] for item in items if item.get("scope_function")
    )
    return {
        "total": len(items),
        "by_archetype": dict(sorted(by_archetype.items())),
        "by_function": dict(sorted(by_function.items())),
        "uses_authority_mcp": sum(1 for item in items if item.get("uses_authority_mcp")),
        "items": items,
    }


def _snapshot_functions() -> list[dict[str, Any]]:
    return [
        {
            "name": fn.name,
            "display": fn.display,
            "operatorSurface": fn.operator_surface,
            "ownsDomains": list(fn.owns_domains),
            "ambientAgents": list(fn.ambient_agents),
            "kpis": list(fn.kpis),
            "personaHierarchy": _persona_tree_to_dict(fn.persona_hierarchy),
        }
        for name, fn in FUNCTIONS.items()
        if name != "legacy"
    ]


def _snapshot_memories() -> dict[str, list[dict[str, Any]]]:
    items: list[dict[str, Any]] = []
    for domain, store in (app_state.domain_memories or {}).items():
        for entry in store.list_by_kind("working"):
            metadata = entry.get("metadata") or {}
            items.append(
                {
                    "id": entry.get("id"),
                    "domain": domain,
                    "memory": entry.get("memory"),
                    "agent_skill": metadata.get("agent_skill", ""),
                    "workflow_id": metadata.get("workflow_id", ""),
                    "captured_at": metadata.get("captured_at", ""),
                    "metadata": metadata,
                }
            )
    items.sort(key=lambda item: item.get("captured_at") or "", reverse=True)
    return {"items": items}


def _snapshot_lessons() -> dict[str, list[dict[str, Any]]]:
    items: list[dict[str, Any]] = []
    for domain, store in (app_state.domain_memories or {}).items():
        for entry in store.list_by_kind("lesson"):
            metadata = entry.get("metadata") or {}
            items.append(
                {
                    "id": entry.get("id"),
                    "domain": domain,
                    "memory": entry.get("memory"),
                    "consolidated_at": metadata.get("consolidated_at", ""),
                    "source": metadata.get("source", "dream-consolidation"),
                    "metadata": metadata,
                }
            )
    items.sort(key=lambda item: item.get("consolidated_at") or "", reverse=True)
    return {"items": items}


def _snapshot_kpis() -> dict[str, Any]:
    kpi_store = getattr(app_state, "kpi_store", None)
    if kpi_store is None or not hasattr(kpi_store, "query"):
        return {"values": []}
    return {"values": kpi_store.query()}


def _snapshot_audit_summary() -> dict[str, Any]:
    audit = getattr(app_state, "audit", None)
    if audit is None or not hasattr(audit, "list"):
        return {"total": 0, "by_action": {}}

    entries = audit.list()
    actions = Counter(entry.get("action") for entry in entries)
    by_action = {
        action: count
        for action, count in sorted(actions.items())
        if action is not None
    }
    return {
        "total": len(entries),
        "by_action": by_action,
    }


def take_snapshot(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    payloads: list[tuple[str, Any]] = [
        ("workflows.json", _snapshot_workflows()),
        ("exceptions.json", _snapshot_exceptions()),
        ("personae.json", _snapshot_personae()),
        ("functions.json", _snapshot_functions()),
        ("memories.json", _snapshot_memories()),
        ("lessons.json", _snapshot_lessons()),
        ("kpis.json", _snapshot_kpis()),
        ("audit_summary.json", _snapshot_audit_summary()),
    ]

    written: list[Path] = []
    for name, payload in payloads:
        path = out_dir / name
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(path)
    return written
