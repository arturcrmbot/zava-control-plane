from api.shared.all_functions import Function, PersonaTree
from api.shared.vertical_loader import active_runtime

__all__ = [
    "FUNCTIONS",
    "Function",
    "PersonaTree",
    "_validate_persona_hierarchy",
    "_wire_function_back_refs",
]


FUNCTIONS = active_runtime().pack.organisation_functions

_LEGACY_SENTINEL = "__legacy__"


def _wire_function_back_refs() -> None:
    from api.shared.domains import DOMAINS

    for function_name, function in FUNCTIONS.items():
        for workflow_type in function.owns_domains:
            if workflow_type not in DOMAINS:
                raise ValueError(
                    f"FUNCTIONS[{function_name!r}] claims unknown domain "
                    f"{workflow_type!r}"
                )
            DOMAINS[workflow_type].function = function_name
    orphans = [
        workflow_type
        for workflow_type, domain in DOMAINS.items()
        if domain.function is None
    ]
    if orphans:
        raise ValueError(f"unclaimed domains (no function owns these): {orphans}")


def _validate_persona_hierarchy() -> None:
    roots = active_runtime().pack.personae_roots

    def walk(node: PersonaTree, function_name: str) -> None:
        if node.role == _LEGACY_SENTINEL:
            return
        if not any((root / node.role / "SKILL.md").is_file() for root in roots):
            raise ValueError(
                f"FUNCTIONS[{function_name!r}].persona_hierarchy references "
                f"unknown persona {node.role!r}"
            )
        for child in node.manages:
            walk(child, function_name)

    for function_name, function in FUNCTIONS.items():
        walk(function.persona_hierarchy, function_name)
