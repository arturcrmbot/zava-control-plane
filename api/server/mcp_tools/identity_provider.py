"""identity_provider MCP tool — RBAC role templates + separation-of-duties screening.

Stub. Returns deterministic synthetic data keyed on the input(s). No real
upstream call. Replace the bodies of `list_role_templates`,
`get_role_template`, `check_separation_of_duties` with real Identity
Provider (Okta / Azure AD / etc.) calls when wiring to a production
tenant.
"""
from __future__ import annotations
import hashlib
import json

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool


# Per-grade template default sizes (the IT Admin compares the proposed
# bundle size against this).
_TEMPLATE_DEFAULT_SIZE_BY_GRADE: dict[str, int] = {
    "G1": 6,
    "G2": 6,
    "G3": 8,
    "G4": 8,
    "G5": 10,
    "G6": 12,
    "G7": 14,
}

# Curated permission pool. Each (department, grade) draws a stable subset
# from this pool keyed on the seed.
_PERMISSION_POOL: list[str] = [
    "files.read",
    "files.write",
    "files.share",
    "mail.send",
    "mail.read",
    "calendar.read",
    "calendar.write",
    "vault.read",
    "vault.write",
    "billing.read",
    "billing.write",
    "billing.approve",
    "vendor.read",
    "vendor.write",
    "vendor.approve",
    "expense.submit",
    "expense.approve",
    "hr.read",
    "hr.write",
    "audit.read",
    "ci.read",
    "ci.deploy",
    "secrets.read",
    "secrets.write",
]

# SoD conflict pairs. If both members of a pair appear in the union, the
# conflict name is reported.
_SOD_CONFLICT_PAIRS: list[tuple[str, str, str]] = [
    ("expense.submit", "expense.approve", "expense.submit_vs_approve"),
    ("billing.write", "billing.approve", "billing.write_vs_approve"),
    ("vendor.write", "vendor.approve", "vendor.write_vs_approve"),
    ("ci.deploy", "secrets.write", "ci.deploy_vs_secrets.write"),
]


# --------------------------------------------------------------------------
# list_role_templates
# --------------------------------------------------------------------------


@traced_tool("identity_provider.list_role_templates")
def list_role_templates(department: str, grade: str) -> dict:
    """List candidate role templates that fit (department, grade) — stub."""
    span = trace.get_current_span()
    span.set_attribute("zava.identity_provider.department", str(department))
    span.set_attribute("zava.identity_provider.grade", str(grade))
    return _synth_list_role_templates(department, grade)


def _synth_list_role_templates(department: str, grade: str) -> dict:
    """Deterministic synthesis. Same (department, grade) -> identical templates."""
    seed = int(hashlib.sha256(f"{department}|{grade}".encode()).hexdigest()[:8], 16)
    n_templates = 2 + (seed % 2)  # 2..3 candidate templates
    template_ids = [
        f"tmpl-{department.lower()[:3]}-{grade.lower()}-{(seed >> (i * 4)) % 100:02d}"
        for i in range(n_templates)
    ]
    default_size = _TEMPLATE_DEFAULT_SIZE_BY_GRADE.get(grade, 8)
    return {
        "department": department,
        "grade": grade,
        "templates": [
            {"template_id": tid, "label": f"{department} default ({grade})"}
            for tid in template_ids
        ],
        "template_default_size": default_size,
    }


class _ListRoleTemplatesParams(BaseModel):
    department: str = Field(description="Joiner department (e.g. Finance, Engineering)")
    grade: str = Field(description="Joiner grade (e.g. G3)")


@define_tool(
    name="identity_provider_list_role_templates",
    description=(
        "List candidate RBAC role templates that fit a given (department, grade) pair, "
        "plus the template_default_size that the IT Admin uses to bound the day-1 bundle. "
        "Use as the first step of access drafting. "
        "Stub: returns deterministic synthetic data."
    ),
)
def identity_provider_list_role_templates_tool(params: _ListRoleTemplatesParams) -> ToolResult:
    try:
        result = list_role_templates(params.department, params.grade)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))


# --------------------------------------------------------------------------
# get_role_template
# --------------------------------------------------------------------------


@traced_tool("identity_provider.get_role_template")
def get_role_template(template_id: str) -> dict:
    """Fetch a single role template's permission list — stub."""
    span = trace.get_current_span()
    span.set_attribute("zava.identity_provider.template_id", str(template_id))
    return _synth_get_role_template(template_id)


def _synth_get_role_template(template_id: str) -> dict:
    """Deterministic synthesis. Same template_id -> identical permission list."""
    seed = int(hashlib.sha256(str(template_id).encode()).hexdigest()[:8], 16)
    n_perms = 4 + (seed % 5)  # 4..8 permissions per template
    pool_size = len(_PERMISSION_POOL)
    indices: list[int] = []
    cursor = seed
    while len(indices) < n_perms:
        idx = cursor % pool_size
        if idx not in indices:
            indices.append(idx)
        cursor = (cursor * 1103515245 + 12345) & 0x7FFFFFFF
    permissions = [_PERMISSION_POOL[i] for i in indices]
    return {
        "template_id": template_id,
        "permissions": permissions,
    }


class _GetRoleTemplateParams(BaseModel):
    template_id: str = Field(description="Role template identifier (e.g. tmpl-fin-g3-04)")


@define_tool(
    name="identity_provider_get_role_template",
    description=(
        "Fetch a single role template's permission list by template_id. "
        "Use once per candidate template returned by "
        "identity_provider_list_role_templates. "
        "Stub: returns deterministic synthetic data."
    ),
)
def identity_provider_get_role_template_tool(params: _GetRoleTemplateParams) -> ToolResult:
    try:
        result = get_role_template(params.template_id)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))


# --------------------------------------------------------------------------
# check_separation_of_duties
# --------------------------------------------------------------------------


@traced_tool("identity_provider.check_separation_of_duties")
def check_separation_of_duties(permissions: list[str]) -> dict:
    """Screen a permission union for SoD conflict pairs — stub."""
    span = trace.get_current_span()
    span.set_attribute("zava.identity_provider.permission_count", len(permissions))
    return _synth_check_separation_of_duties(permissions)


def _synth_check_separation_of_duties(permissions: list[str]) -> dict:
    """Pure rule check. Same input set -> identical conflict list."""
    perm_set = set(permissions or [])
    conflicts = [
        name for (a, b, name) in _SOD_CONFLICT_PAIRS
        if a in perm_set and b in perm_set
    ]
    return {
        "permission_count": len(perm_set),
        "conflicts": conflicts,
    }


class _CheckSeparationOfDutiesParams(BaseModel):
    permissions: list[str] = Field(
        description="Union of permission strings to screen for conflict pairs",
    )


@define_tool(
    name="identity_provider_check_separation_of_duties",
    description=(
        "Screen a union of permissions for separation-of-duties conflict pairs. "
        "Returns a list of conflict names; empty list means the bundle is clean. "
        "Use after composing the union of role-template permissions. "
        "Stub: returns deterministic synthetic data."
    ),
)
def identity_provider_check_separation_of_duties_tool(
    params: _CheckSeparationOfDutiesParams,
) -> ToolResult:
    try:
        result = check_separation_of_duties(params.permissions)
        return ToolResult(text_result_for_llm=json.dumps(result, ensure_ascii=False))
    except Exception as ex:
        return ToolResult(text_result_for_llm="", result_type="failure", error=str(ex))
