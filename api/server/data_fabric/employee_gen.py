"""api/server/data_fabric/employee_gen.py — synthetic Person generator.

Walks every ``api.shared.functions.FUNCTIONS[fn].persona_hierarchy`` to
produce ~100 named ``GeneratedEmployee`` rows. The hierarchy supplies
the org-chart spine (manager links). Names come from Faker (``en_GB``
locale). Subsidiary, region and ``employed_from`` are drawn from a
seeded ``random.Random`` so the output is fully deterministic.

Plan: plan/feature-enterprise-pitch-readiness-1.md (task ``pitch-b2``).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from faker import Faker

from api.shared.functions import FUNCTIONS, PersonaTree

# 5 named subsidiaries — distribution target is ~even across these.
SUBSIDIARIES: tuple[str, ...] = (
    "ORG-zava-creative",
    "ORG-zava-media",
    "ORG-zava-production",
    "ORG-zava-data",
    "ORG-zava-group",
)

# Region distribution. Hard-coded here (b8's locales registry may not
# exist when this module is imported during the parallel pitch sprint).
_REGION_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("UK", 0.60),
    ("US", 0.20),
    ("DE", 0.10),
    ("FR", 0.05),
    ("JP", 0.05),
)

# Function name -> human-readable department label used on the row.
_DEPARTMENT_LABEL: dict[str, str] = {
    "finance": "Finance",
    "hr": "People",
    "revenue": "Revenue",
    "ops": "Operations",
    "legal": "Legal",
    "marketing": "Creative",
    "tech": "Tech",
    "data": "Data",
    "customer-success": "Customer Success",
    "ceo": "Strategy",
    "legacy": "Shared Services",
}

_EMAIL_DOMAIN = "zava.example"
_EMPLOYED_FROM_START = date(2020, 1, 1)


@dataclass(frozen=True)
class GeneratedEmployee:
    id: str
    name: str
    email: str
    department: str
    persona_role: str
    function: str
    region: str
    employed_from: date
    manager_id: str | None
    subsidiary: str


def _slugify_email_local(name: str, rng: random.Random) -> str:
    parts = [p for p in name.lower().replace("'", "").replace(".", "").split() if p]
    if len(parts) < 2:
        parts.append(str(rng.randint(10, 99)))
    return f"{parts[0]}.{parts[-1]}"


def _weighted_region(rng: random.Random) -> str:
    regions = [r for r, _ in _REGION_WEIGHTS]
    weights = [w for _, w in _REGION_WEIGHTS]
    return rng.choices(regions, weights=weights, k=1)[0]


def _weighted_employed_from(rng: random.Random, today: date) -> date:
    """Random date in [2020-01-01, today], weighted toward more recent."""
    span_days = (today - _EMPLOYED_FROM_START).days
    if span_days <= 0:
        return today
    # Square the uniform draw and invert so the density rises toward today.
    u = rng.random()
    offset = int(span_days * (1.0 - u * u))
    return _EMPLOYED_FROM_START + timedelta(days=offset)


def _walk_roles(node: PersonaTree) -> list[tuple[str, str | None]]:
    """Depth-first list of (role, parent_role) pairs from a PersonaTree."""
    out: list[tuple[str, str | None]] = []

    def _dfs(n: PersonaTree, parent: str | None) -> None:
        out.append((n.role, parent))
        for child in n.manages:
            _dfs(child, n.role)

    _dfs(node, None)
    return out


def generate_employees(*, seed: int = 42, count: int = 100) -> list[GeneratedEmployee]:
    """Materialise ``count`` synthetic employees.

    For each function in ``FUNCTIONS`` the persona hierarchy is walked
    depth-first; the root role gets exactly one Person (no manager),
    every other role gets at least one Person whose ``manager_id``
    points at the most-recently-generated Person carrying its parent
    role within the same function. Once every function has at least one
    employee per role, additional employees are spread across non-root
    roles (round-robin) until the total reaches ``count``.

    The returned list is sorted by ``id``. Output is deterministic for a
    given ``seed``.
    """
    rng = random.Random(seed)
    fake = Faker(locale="en_GB")
    fake.seed_instance(seed)

    today = date.today()
    employees: list[GeneratedEmployee] = []
    used_emails: set[str] = set()

    # Per-(function, role) -> list of generated PERSON ids in insertion order.
    role_index: dict[tuple[str, str], list[str]] = {}

    # Preserve registry insertion order for deterministic walks.
    fn_items = list(FUNCTIONS.items())

    def _next_id() -> str:
        return f"PERSON-EMP-{len(employees) + 1:04d}"

    def _make_employee(fn_name: str, role: str, parent_role: str | None) -> GeneratedEmployee:
        emp_id = _next_id()
        # Unique email — retry up to a few times before falling back to a
        # numeric suffix derived from the employee id.
        for _ in range(8):
            name = fake.name()
            local = _slugify_email_local(name, rng)
            email = f"{local}@{_EMAIL_DOMAIN}"
            if email not in used_emails:
                break
        else:
            name = fake.name()
            local = _slugify_email_local(name, rng)
            email = f"{local}.{len(employees) + 1}@{_EMAIL_DOMAIN}"
        used_emails.add(email)

        manager_id: str | None = None
        if parent_role is not None:
            parents = role_index.get((fn_name, parent_role))
            if parents:
                manager_id = parents[-1]

        subsidiary = SUBSIDIARIES[len(employees) % len(SUBSIDIARIES)]
        region = _weighted_region(rng)
        employed_from = _weighted_employed_from(rng, today)

        emp = GeneratedEmployee(
            id=emp_id,
            name=name,
            email=email,
            department=_DEPARTMENT_LABEL.get(fn_name, fn_name.title()),
            persona_role=role,
            function=fn_name,
            region=region,
            employed_from=employed_from,
            manager_id=manager_id,
            subsidiary=subsidiary,
        )
        employees.append(emp)
        role_index.setdefault((fn_name, role), []).append(emp_id)
        return emp

    # Pass 1 — one Person per (function, role) following the hierarchy.
    for fn_name, fn in fn_items:
        for role, parent in _walk_roles(fn.persona_hierarchy):
            if len(employees) >= count:
                break
            _make_employee(fn_name, role, parent)
        if len(employees) >= count:
            break

    # Pass 2 — round-robin extra Persons across non-root roles until we
    # hit ``count``. Roots are skipped so we don't manufacture multiple
    # CFOs/CPOs/etc.; if the registry has so few non-root roles that we
    # can't reach ``count`` we fall back to roots too.
    expansion_targets: list[tuple[str, str, str | None]] = []
    expansion_roots: list[tuple[str, str, str | None]] = []
    for fn_name, fn in fn_items:
        for role, parent in _walk_roles(fn.persona_hierarchy):
            entry = (fn_name, role, parent)
            if parent is None:
                expansion_roots.append(entry)
            else:
                expansion_targets.append(entry)

    pool = expansion_targets if expansion_targets else expansion_roots
    i = 0
    while len(employees) < count and pool:
        fn_name, role, parent = pool[i % len(pool)]
        _make_employee(fn_name, role, parent)
        i += 1
        if i > count * 10:  # defensive guard
            break

    employees.sort(key=lambda e: e.id)
    return employees
