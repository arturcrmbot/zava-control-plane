from __future__ import annotations

import json
from dataclasses import replace
from importlib import import_module
from pathlib import Path
from typing import Any

from api.shared.projection_contracts import ProjectionFn
from api.shared.vertical_pack import VerticalUiManifest


def lazy_projection(module_name: str) -> ProjectionFn:
    def project(workflow):
        return import_module(module_name).project(workflow)

    return project


def wire_domain_functions(domains: dict, functions: dict) -> dict:
    owners: dict[str, str] = {}
    for function in functions.values():
        for workflow_type in function.owns_domains:
            if workflow_type in owners:
                raise ValueError(
                    f"domain {workflow_type!r} has multiple function owners"
                )
            owners[workflow_type] = function.name
    if set(owners) != set(domains):
        raise ValueError(
            "function ownership mismatch: "
            f"missing={sorted(set(domains) - set(owners))}, "
            f"unknown={sorted(set(owners) - set(domains))}"
        )
    return {
        workflow_type: replace(domain, function=owners[workflow_type])
        for workflow_type, domain in domains.items()
    }


def load_ui_manifest(path: Path) -> VerticalUiManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "capabilities",
        "lenses",
        "theme",
        "phase_aliases",
        "aspirational_domains",
        "include_meta_skills",
    }
    unknown = sorted(set(data) - expected)
    if unknown:
        raise ValueError(f"unknown UI manifest keys: {unknown}")
    return VerticalUiManifest(
        capabilities=frozenset(data["capabilities"]),
        lenses=tuple(data["lenses"]),
        theme=data["theme"],
        phase_aliases=data["phase_aliases"],
        aspirational_domains=tuple(data.get("aspirational_domains", ())),
        include_meta_skills=bool(data.get("include_meta_skills", False)),
    )


async def empty_lifecycle(_state: Any):
    return ()


def empty_seed(_state: Any) -> None:
    return None
