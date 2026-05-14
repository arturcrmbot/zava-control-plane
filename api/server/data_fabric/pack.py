"""DataPack — typed, deterministic seeder for the Zava entity graph.

Single Python entrypoint that orchestrates every Plane-1 generator in
``api.server.data_fabric.*`` and writes the result to a fresh Kuzu DB at
the requested path. The output is intended to be snapshotted via
``scripts/zava-snapshot.py`` so a cold-start demo can rehydrate in seconds
instead of waiting for the live simulator to ramp.

Plan: plan/feature-enterprise-pitch-readiness-1.md (tasks ``pitch-b9`` /
``pitch-b10`` / ``pitch-e3``). Brand nodes still project onto
``Organisation(kind='brand')`` until brand materialisation is rewritten
against the e1 first-class :class:`Brand` table; subsidiaries (e3) now
land as both ``Organisation(kind='subsidiary'|'holding')`` AND
first-class :class:`Subsidiary` nodes, with PART_OF edges from each
non-holding subsidiary to ``ORG-zava-group``.
"""

from __future__ import annotations

import json
import logging
import random
import shutil
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from api.server.data_fabric.asset_gen import generate_assets
from api.server.data_fabric.calendar import all_periods
from api.server.data_fabric.client_brand_gen import generate_clients_and_brands
from api.server.data_fabric.employee_gen import SUBSIDIARIES, generate_employees
from api.server.data_fabric.money_gen import generate_money
from api.server.data_fabric.vendor_gen import generate_vendors
from api.server.data_fabric.workflow_timeline import generate_timeline
from api.server.services.decision_vocab import canonical_verdict
from api.server.services.entity_graph import (
    DecisionWrite,
    EntityGraph,
    EntityWrite,
    RelWrite,
)
from api.server.services.entity_projections import PROJECTIONS

__all__ = ["DataPack", "build_zava_pack"]

log = logging.getLogger(__name__)


# Region → (place_id, country, jurisdiction). Place nodes are created
# once per region; every employee LOCATED_IN one of these.
_REGION_PLACES: dict[str, tuple[str, str, str]] = {
    "UK": ("PLACE-UK", "United Kingdom", "UK"),
    "US": ("PLACE-US", "United States", "US"),
    "DE": ("PLACE-DE", "Germany", "EU"),
    "FR": ("PLACE-FR", "France", "EU"),
    "ES": ("PLACE-ES", "Spain", "EU"),
    "IT": ("PLACE-IT", "Italy", "EU"),
    "JP": ("PLACE-JP", "Japan", "JP"),
    "IN": ("PLACE-IN", "India", "IN"),
    "BR": ("PLACE-BR", "Brazil", "BR"),
    "AU": ("PLACE-AU", "Australia", "AU"),
}


# Per-subsidiary metadata for the e3 first-class Subsidiary nodes.
# Each entry: (id, display_name, country, headcount). The "ORG-zava-group"
# id stays as a plain Organisation (kind="holding"); the other 4 are
# materialised as Subsidiary nodes and PART_OF →ORG-zava-group.
_SUBSIDIARY_META: tuple[tuple[str, str, str, int], ...] = (
    ("ORG-zava-creative",   "Zava Creative",   "UK", 20),
    ("ORG-zava-media",      "Zava Media",      "US", 20),
    ("ORG-zava-production", "Zava Production", "DE", 20),
    ("ORG-zava-data",       "Zava Data",       "UK", 20),
    ("ORG-zava-group",      "Zava Group",      "UK", 20),
)
_HOLDING_ID = "ORG-zava-group"


_GL_ACCOUNTS: tuple[tuple[str, str, str, str], ...] = (
    # (id, code, name, type)
    ("ACC-4000", "4000", "Revenue — fee income",         "revenue"),
    ("ACC-4100", "4100", "Revenue — media commission",   "revenue"),
    ("ACC-6010", "6010", "Production cost — external",   "expense"),
    ("ACC-6020", "6020", "Freelance talent",             "expense"),
    ("ACC-6100", "6100", "Media buys (pass-through)",    "expense"),
    ("ACC-7000", "7000", "Salaries & benefits",          "expense"),
    ("ACC-7200", "7200", "Travel & entertainment",       "expense"),
    ("ACC-7300", "7300", "Software & subscriptions",     "expense"),
    ("ACC-8500", "8500", "FX gains/losses",              "other"),
    ("ACC-9000", "9000", "Intercompany recharge",        "intercompany"),
)

# Money kind → GL account id mapping
_KIND_TO_ACCOUNT: dict[str, str] = {
    "invoice":     "ACC-6010",
    "po":          "ACC-6010",  # PO commitment hits same expense bucket
    "contract":    "ACC-6010",
    "commission":  "ACC-4100",
    "fx":          "ACC-8500",
    "fx-adj":      "ACC-8500",
    "recharge":    "ACC-9000",
    "budget-line": "ACC-6010",
}


@dataclass(frozen=True)
class DataPack:
    """Typed bundle of generator parameters + a single ``materialise()`` call.

    ``materialise()`` is idempotent (it deletes the target Kuzu directory
    first), and fully deterministic for a given ``seed``: two
    materialisations with the same seed produce graphs with identical
    node + edge counts.
    """

    name: str
    seed: int
    fiscal_year: int
    employee_count: int = 100
    vendor_count: int = 50
    client_count: int = 6
    asset_count: int = 150
    money_count: int = 750
    historical_workflow_count: int = 125
    in_flight_workflow_count: int = 25

    # ------------------------------------------------------------------ public

    def materialise(self, kuzu_path: str | Path) -> dict:
        """Build the full graph from generators and write to Kuzu at ``kuzu_path``.

        Returns a dict ``{node_count, edge_count, generator_summary,
        fiscal_year}``. Idempotent: deletes the ``kuzu_path`` directory if
        it exists, then constructs a fresh :class:`EntityGraph`.
        """
        kuzu_dir = Path(kuzu_path)
        if kuzu_dir.exists():
            log.info("pack.materialise: wiping existing kuzu dir %s", kuzu_dir)
            shutil.rmtree(kuzu_dir)

        summary: dict[str, int] = {}
        rng = random.Random(self.seed)

        graph = EntityGraph(kuzu_dir)
        try:
            summary["periods"] = self._write_periods(graph)
            summary["subsidiaries"] = self._write_subsidiaries(graph)
            summary["accounts"] = self._write_accounts(graph)
            summary["cost_centres"] = self._write_cost_centres(graph)
            summary["places"] = self._write_places(graph)

            clients, brands = generate_clients_and_brands(
                seed=self.seed, client_count=self.client_count
            )
            summary["clients"] = self._write_clients(graph, clients)
            summary["brands"] = self._write_brands(graph, brands)

            vendors = generate_vendors(seed=self.seed, count=self.vendor_count)
            summary["vendors"] = self._write_vendors(graph, vendors)

            employees = generate_employees(
                seed=self.seed, count=self.employee_count
            )
            emp_links = self._write_employees(graph, employees)
            summary["employees"] = len(employees)
            summary["employed_by_links"] = emp_links["employed_by"]
            summary["manages_links"] = emp_links["manages"]
            summary["located_in_links"] = emp_links["located_in"]

            assets = generate_assets(
                seed=self.seed,
                brands=brands,
                clients=clients,
                subsidiaries=list(SUBSIDIARIES),
                count=self.asset_count,
            )
            asset_links = self._write_assets(graph, assets, employees, rng)
            summary["assets"] = len(assets)
            summary["owns_links"] = asset_links

            period_ids = [p["id"] for p in all_periods(self.fiscal_year)]
            money_rows = generate_money(
                seed=self.seed,
                brands=brands,
                clients=clients,
                vendors=vendors,
                subsidiaries=list(SUBSIDIARIES),
                period_ids=period_ids,
                count=self.money_count,
            )
            money_links = self._write_money(graph, money_rows, employees, rng)
            summary["money"] = len(money_rows)
            summary["belongs_to_links"] = money_links["belongs_to"]
            summary["transacts_links"] = money_links["transacts"]

            timeline = generate_timeline(
                seed=self.seed,
                in_flight_count=self.in_flight_workflow_count,
                historical_count=self.historical_workflow_count,
            )
            wf_summary = self._write_workflows(graph, timeline)
            summary["workflows"] = wf_summary["workflows"]
            summary["sub_workflow_links"] = wf_summary["sub_workflow_of"]

            from scripts.backfill_workflow_periods import backfill as _backfill_periods
            wp_summary = _backfill_periods(graph)
            summary["workflow_in_period_links"] = wp_summary["workflow_in_period"]

            decision_summary = self._write_decisions(
                graph, timeline, employees, rng
            )
            summary["decisions"] = decision_summary["decisions"]
            summary["decided_links"] = decision_summary["decided_links"]
            summary["precedent_links"] = decision_summary["precedent"]

            from scripts.backfill_money_org_edges import backfill
            money_edges = backfill(graph)
            summary["pays_links"] = money_edges["pays"]
            summary["owed_by_links"] = money_edges["owed_by"]
            summary["costed_to_brand_links"] = money_edges["costed_to_brand"]

            counts = graph.count_by_kind()
            node_count = sum(counts.values())
            edge_count = self._count_edges(graph)
        finally:
            graph.close()

        result = {
            "node_count": node_count,
            "edge_count": edge_count,
            "generator_summary": summary,
            "fiscal_year": self.fiscal_year,
        }
        log.info("pack.materialise: %s", result)
        return result

    # ----------------------------------------------------------- write helpers

    def _write_periods(self, graph: EntityGraph) -> int:
        periods = all_periods(self.fiscal_year)
        for p in periods:
            graph.upsert(
                EntityWrite(
                    kind="Period",
                    id=p["id"],
                    attrs={
                        "kind": p["kind"],
                        "starts": _to_dt(p["starts"]),
                        "ends": _to_dt(p["ends"]),
                        "label": p["label"],
                    },
                )
            )
        log.debug("pack: wrote %d periods", len(periods))
        return len(periods)

    def _write_subsidiaries(self, graph: EntityGraph) -> int:
        """Write 5 named subsidiaries.

        Each id is materialised twice:
          1. as an Organisation (kind="subsidiary"/"holding") so the
             existing Person→Organisation EMPLOYED_BY edges keep linking
             cleanly — the schema requires Organisation as the target;
          2. as a first-class :class:`Subsidiary` node (pitch-e1 schema)
             carrying ``country`` + ``headcount``, with a
             ``Subsidiary -[:PART_OF]→ Organisation`` edge to the
             ``ORG-zava-group`` holding id (4 PART_OF edges total — the
             group node is its own holding so it doesn't link to itself).
        """
        for sub_id, name, country, headcount in _SUBSIDIARY_META:
            org_kind = "holding" if sub_id == _HOLDING_ID else "subsidiary"
            graph.upsert(
                EntityWrite(
                    kind="Organisation",
                    id=sub_id,
                    attrs={
                        "name": name,
                        "kind": org_kind,
                        "country": country,
                        "jurisdiction": country,
                        "risk_band": "green",
                        "attributes": json.dumps({"role": org_kind}),
                    },
                )
            )
            graph.upsert(
                EntityWrite(
                    kind="Subsidiary",
                    id=sub_id,
                    attrs={
                        "name": name,
                        "country": country,
                        "headcount": headcount,
                        "attributes": json.dumps({"role": org_kind}),
                    },
                )
            )
        # Second pass — every PART_OF endpoint is now guaranteed to exist
        # in both the Subsidiary and Organisation tables, so the typed
        # MATCH can find them. Typed because the same id lives in BOTH
        # tables (we materialise each subsidiary id twice);
        # ``graph.link``'s untyped ``MATCH (a), (b)`` can't disambiguate
        # which would collapse the MERGE to zero rows.
        for sub_id, *_rest in _SUBSIDIARY_META:
            if sub_id == _HOLDING_ID:
                continue
            graph.conn.execute(
                "MATCH (s:Subsidiary), (o:Organisation) "
                "WHERE s.id = $src AND o.id = $dst "
                "MERGE (s)-[:PART_OF]->(o)",
                {"src": sub_id, "dst": _HOLDING_ID},
            )
        log.debug(
            "pack: wrote %d subsidiaries (Organisation+Subsidiary pairs, "
            "4 PART_OF→%s)",
            len(_SUBSIDIARY_META), _HOLDING_ID,
        )
        return len(_SUBSIDIARY_META)

    def _write_accounts(self, graph: EntityGraph) -> int:
        for acc_id, code, name, type_ in _GL_ACCOUNTS:
            graph.upsert(EntityWrite(
                kind="Account", id=acc_id,
                attrs={"code": code, "name": name, "type": type_, "currency": "GBP"},
            ))
        return len(_GL_ACCOUNTS)


    def _write_cost_centres(self, graph: EntityGraph) -> int:
        # Skip the holding (ORG-zava-group) — holdings don't take cost.
        n = 0
        for sub_id, name, country, _ in _SUBSIDIARY_META:
            if sub_id == _HOLDING_ID:
                continue
            cc_id = sub_id.replace("ORG-", "CC-")
            graph.upsert(EntityWrite(
                kind="CostCentre", id=cc_id,
                attrs={"name": name, "subsidiary_id": sub_id, "owner_role": "regional_account_lead"},
            ))
            n += 1
        return n

    def _write_places(self, graph: EntityGraph) -> int:
        for place_id, name, jurisdiction in _REGION_PLACES.values():
            graph.upsert(
                EntityWrite(
                    kind="Place",
                    id=place_id,
                    attrs={
                        "kind": "country",
                        "name": name,
                        "parent_id": "",
                        "attributes": json.dumps(
                            {"jurisdiction": jurisdiction}
                        ),
                    },
                )
            )
        log.debug("pack: wrote %d places", len(_REGION_PLACES))
        return len(_REGION_PLACES)

    def _write_clients(self, graph: EntityGraph, clients: list) -> int:
        for c in clients:
            graph.upsert(
                EntityWrite(
                    kind="Organisation",
                    id=c.id,
                    attrs={
                        "name": c.name,
                        "kind": "client",
                        "country": c.region,
                        "jurisdiction": c.region,
                        "risk_band": "green",
                        "attributes": json.dumps(
                            {
                                "tier": c.tier,
                                "industry": c.industry,
                                "annual_revenue_gbp": c.annual_revenue_gbp,
                            }
                        ),
                    },
                )
            )
        return len(clients)

    def _write_brands(self, graph: EntityGraph, brands: list) -> int:
        for b in brands:
            graph.upsert(EntityWrite(
                kind="Brand", id=b.id,
                attrs={
                    "name": b.name,
                    "market_segment": b.market_segment,
                    "annual_budget_gbp": float(b.annual_budget_gbp),
                    "budget_remaining_gbp": float(b.annual_budget_gbp),
                },
            ))
            graph.conn.execute(
                "MATCH (b:Brand), (o:Organisation) "
                "WHERE b.id = $b AND o.id = $o "
                "MERGE (b)-[:BRAND_OF]->(o)",
                {"b": b.id, "o": b.client_id},
            )
        return len(brands)

    def _write_vendors(self, graph: EntityGraph, vendors: list) -> int:
        for v in vendors:
            graph.upsert(
                EntityWrite(
                    kind="Organisation",
                    id=v.id,
                    attrs={
                        "name": v.name,
                        "kind": "vendor",
                        "country": v.country,
                        "jurisdiction": v.country,
                        "risk_band": v.risk_band,
                        "attributes": json.dumps(
                            {
                                "subkind": v.subkind,
                                "payment_terms_days": v.payment_terms_days,
                                "esg_rating": v.esg_rating,
                                "is_blocked": v.is_blocked,
                            }
                        ),
                    },
                )
            )
        return len(vendors)

    def _write_employees(
        self, graph: EntityGraph, employees: list
    ) -> dict[str, int]:
        employed_by = 0
        manages = 0
        located_in = 0
        for emp in employees:
            graph.upsert(
                EntityWrite(
                    kind="Person",
                    id=emp.id,
                    attrs={
                        "name": emp.name,
                        "email": emp.email,
                        "role": emp.persona_role,
                        "market": emp.region,
                        "department": emp.department,
                        "employed_from": emp.employed_from,
                    },
                )
            )
            graph.link(
                emp.id, "EMPLOYED_BY", emp.subsidiary,
                role=emp.persona_role,
                since=emp.employed_from,
            )
            employed_by += 1

            if emp.manager_id:
                graph.link(
                    emp.manager_id, "MANAGES", emp.id,
                    since=emp.employed_from,
                )
                manages += 1

            place_id = _REGION_PLACES.get(emp.region, _REGION_PLACES["UK"])[0]
            graph.link(emp.id, "LOCATED_IN", place_id)
            located_in += 1
        log.debug(
            "pack: wrote %d employees (%d EMPLOYED_BY, %d MANAGES, "
            "%d LOCATED_IN)",
            len(employees), employed_by, manages, located_in,
        )
        return {
            "employed_by": employed_by,
            "manages": manages,
            "located_in": located_in,
        }

    def _write_assets(
        self,
        graph: EntityGraph,
        assets: list,
        employees: list,
        rng: random.Random,
    ) -> int:
        # TODO(e1): Asset→Brand and Asset→Subsidiary rels need new rel
        # tables (BELONGS_TO currently only Money→Period). For now we
        # only land Person→Asset OWNS edges and store the brand /
        # client / subsidiary FKs in the Asset.attributes blob.
        owns = 0
        for asset in assets:
            graph.upsert(
                EntityWrite(
                    kind="Asset",
                    id=asset.id,
                    attrs={
                        "kind": asset.kind,
                        "identifier": asset.name,
                        "status": asset.status,
                        "attributes": json.dumps(
                            {
                                "brand_id": asset.brand_id,
                                "client_id": asset.client_id,
                                "subsidiary_id": asset.subsidiary_id,
                            }
                        ),
                    },
                )
            )
            if employees:
                owner = employees[rng.randint(0, len(employees) - 1)]
                graph.link(owner.id, "OWNS", asset.id)
                owns += 1
        log.debug("pack: wrote %d assets (%d OWNS)", len(assets), owns)
        return owns

    def _write_money(
        self,
        graph: EntityGraph,
        money_rows: list,
        employees: list,
        rng: random.Random,
    ) -> dict[str, int]:
        belongs_to = 0
        transacts = 0
        for m in money_rows:
            graph.upsert(
                EntityWrite(
                    kind="Money",
                    id=m.id,
                    attrs={
                        "amount": m.amount,
                        "currency": m.currency,
                        "kind": m.kind,
                        "period": m.period_id,
                        "attributes": json.dumps(
                            {
                                "brand_id": m.brand_id,
                                "client_id": m.client_id,
                                "vendor_id": m.vendor_id,
                                "subsidiary_id": m.subsidiary_id,
                            }
                        ),
                    },
                )
            )
            account_id = _KIND_TO_ACCOUNT.get(m.kind, "ACC-6010")
            graph.conn.execute(
                "MATCH (m:Money), (a:Account) WHERE m.id = $m AND a.id = $a "
                "MERGE (m)-[:BOOKED_AGAINST]->(a)",
                {"m": m.id, "a": account_id},
            )
            # Holding subsidiary has no CostCentre — _write_cost_centres
            # skips _HOLDING_ID — so holding-routed Money rows don't get
            # a COSTED_TO. (GeneratedMoney exposes .subsidiary_id, not
            # .subsidiary — getattr keeps this safe if a future kind
            # ships without one.)
            sub_id = getattr(m, "subsidiary_id", None)
            if sub_id and sub_id != _HOLDING_ID:
                cc_id = sub_id.replace("ORG-", "CC-")
                graph.conn.execute(
                    "MATCH (m:Money), (c:CostCentre) WHERE m.id = $m AND c.id = $c "
                    "MERGE (m)-[:COSTED_TO]->(c)",
                    {"m": m.id, "c": cc_id},
                )
            graph.link(m.id, "BELONGS_TO", m.period_id)
            belongs_to += 1
            if employees:
                # Each Money gets 4 TRANSACTS edges — buyer / approver /
                # payer / reviewer — so the graph carries enough
                # provenance for precedent / blast-radius queries to
                # chew on.
                for role in ("buyer", "approver", "payer", "reviewer"):
                    person = employees[rng.randint(0, len(employees) - 1)]
                    graph.link(person.id, "TRANSACTS", m.id, role=role)
                    transacts += 1
        log.debug(
            "pack: wrote %d money rows (%d BELONGS_TO, %d TRANSACTS)",
            len(money_rows), belongs_to, transacts,
        )
        return {"belongs_to": belongs_to, "transacts": transacts}

    def _write_workflows(
        self, graph: EntityGraph, timeline: list
    ) -> dict[str, int]:
        sub_links = 0
        # Map workflow_type -> list of completed wf ids (acts as parents
        # for in-flight ones of the same type).
        completed_by_type: dict[str, list[str]] = {}
        for entry in timeline:
            wf = entry.workflow
            attrs: dict[str, Any] = {
                "workflow_type": wf.type,
                "status": wf.status,
                "started_at": _to_dt(entry.spawned_at),
            }
            if entry.completed_at is not None:
                attrs["completed_at"] = _to_dt(entry.completed_at)
            graph.upsert(
                EntityWrite(kind="Workflow", id=wf.id, attrs=attrs)
            )
            if entry.completed:
                completed_by_type.setdefault(wf.type, []).append(wf.id)

            # High-volume workflow types (~hundreds of timeline rows each)
            # blow up reseed time when run through projections; their
            # decisions are still written by _write_decisions below.
            if wf.type in {"ap-invoice", "it-access-request", "purchase-order"}:
                continue

            projection = PROJECTIONS.get(wf.type)
            if projection is not None:
                for op in projection(entry.workflow):
                    # Skip Money EntityWrites: DataPack._write_money owns the
                    # Money/BOOKED_AGAINST invariant (every Money row booked
                    # to a GL Account). Projection-emitted Money would land
                    # unbooked and break test_every_money_row_booked.
                    if isinstance(op, EntityWrite) and op.kind == "Money":
                        continue
                    try:
                        if isinstance(op, EntityWrite):
                            graph.upsert(op)
                        elif isinstance(op, RelWrite):
                            graph.link(op.src_id, op.rel, op.dst_id, **op.attrs)
                        elif isinstance(op, DecisionWrite):
                            decided_at = op.decided_at
                            if isinstance(decided_at, str):
                                from datetime import datetime as _dt
                                decided_at = _dt.fromisoformat(decided_at) if decided_at else _dt.utcnow()
                            graph.record_decision(
                                workflow_id=op.workflow_id,
                                phase=op.phase,
                                persona_role=op.persona_role,
                                verdict=op.verdict,
                                reason=op.reason,
                                decided_at=decided_at,
                                source_event=op.source_event,
                                attributes=op.attributes,
                                decided_on=op.decided_on,
                            )
                    except Exception as exc:
                        log.warning(
                            "pack: projection op for %s failed: %s",
                            wf.type, exc,
                        )

        # SUB_WORKFLOW_OF: link each in-flight workflow to the most
        # recent completed parent of the same type, if any.
        for entry in timeline:
            if entry.completed:
                continue
            parents = completed_by_type.get(entry.workflow.type, [])
            if not parents:
                continue
            graph.link(
                entry.workflow.id,
                "SUB_WORKFLOW_OF",
                parents[-1],
                spawned_at=_to_dt(entry.spawned_at),
            )
            sub_links += 1
        log.debug(
            "pack: wrote %d workflows (%d SUB_WORKFLOW_OF)",
            len(timeline), sub_links,
        )
        return {"workflows": len(timeline), "sub_workflow_of": sub_links}

    def _write_decisions(
        self,
        graph: EntityGraph,
        timeline: list,
        employees: list,
        rng: random.Random,
    ) -> dict[str, int]:
        # Two decisions per workflow ("intake" + "approve") so precedent
        # search has multi-phase stories to walk. Persona role is picked
        # from the employee pool so TOUCHED edges land too.
        decisions = 0
        decided_links = 0
        precedent_links = 0
        # Track the previous decision id per (workflow_type, phase) to
        # build PRECEDENT_OF chains.
        prev_by_phase: dict[tuple[str, str], str] = {}
        period_ids = [p["id"] for p in all_periods(self.fiscal_year)]

        # Plan task 1.3: persona_role is a ROLE STRING ("ap_clerk"), not a
        # Person id. The actual decider's id moves to attributes.decider_id
        # so TOUCHED edges and provenance are preserved without polluting
        # the role column.
        persona_pool = [(e.id, e.persona_role) for e in employees]
        person_ids = [pid for pid, _ in persona_pool]  # kept for decided_on picking below
        for entry in timeline:
            wf = entry.workflow
            # Plan task 1.2: canonical verdict — "approve", not "approved".
            for phase, verdict in (("intake", canonical_verdict("approve")),
                                   ("approve", canonical_verdict("approve"))):
                if persona_pool:
                    decider_id, persona = persona_pool[rng.randint(0, len(persona_pool) - 1)]
                else:
                    decider_id, persona = f"PERSON-stub-{wf.type}", f"PERSONA-{wf.type}"
                # decided_on: a couple of Person + Period targets that
                # already exist in the graph. Workflow nodes aren't a
                # valid DECIDED target (no rel table), so we route via
                # the persona + period pool instead.
                decided_on: list[str] = []
                if person_ids:
                    decided_on.append(
                        person_ids[rng.randint(0, len(person_ids) - 1)]
                    )
                    decided_on.append(
                        person_ids[rng.randint(0, len(person_ids) - 1)]
                    )
                if period_ids:
                    decided_on.append(
                        period_ids[rng.randint(0, len(period_ids) - 1)]
                    )
                decided_at = _to_dt(entry.spawned_at)
                decision_id = graph.record_decision(
                    workflow_id=wf.id,
                    phase=phase,
                    persona_role=persona,
                    verdict=verdict,
                    reason=f"{wf.type} {phase} via DataPack seed",
                    decided_at=decided_at,
                    source_event=f"datapack.{wf.type}.{phase}",
                    attributes={"workflow_type": wf.type, "decider_id": decider_id},
                    decided_on=tuple(decided_on),
                )
                decisions += 1
                decided_links += len(decided_on)

                key = (wf.type, phase)
                prev_id = prev_by_phase.get(key)
                if prev_id is not None:
                    graph.link(prev_id, "PRECEDENT_OF", decision_id)
                    precedent_links += 1
                prev_by_phase[key] = decision_id
        log.debug(
            "pack: wrote %d decisions (%d DECIDED_*, %d PRECEDENT_OF)",
            decisions, decided_links, precedent_links,
        )
        return {
            "decisions": decisions,
            "decided_links": decided_links,
            "precedent": precedent_links,
        }

    # ----------------------------------------------------------- counters

    def _count_edges(self, graph: EntityGraph) -> int:
        total = 0
        for row in graph.rel_counts():
            total += int(row.get("count", 0))
        return total


def build_zava_pack(seed: int = 42) -> DataPack:
    """Canonical Zava agency-holding pack. Returns a DataPack ready to materialise."""
    return DataPack(name="zava", seed=seed, fiscal_year=2026)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_dt(value: Any) -> datetime:
    """Coerce a date or datetime to a naive datetime suitable for Kuzu TIMESTAMP."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, date):
        return datetime.combine(value, time(0, 0))
    raise TypeError(f"cannot coerce {type(value)!r} to datetime")
