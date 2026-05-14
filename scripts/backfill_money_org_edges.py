"""scripts/backfill_money_org_edges.py — one-shot backfill.

Reads Money.attributes JSON and writes:
  - PAYS    (Money→Organisation) when attributes.vendor_id is set
  - OWED_BY (Money→Organisation) when attributes.client_id is set

Both writes use Kuzu's MERGE semantics so re-running is a no-op. Designed
to be run after `EntityGraph` schema has been extended with the rel
tables (Plan task 2.2).

Usage:
    python -m scripts.backfill_money_org_edges \
        --kuzu data/portal/entity_graph.kuzu
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from api.server.services.entity_graph import EntityGraph

log = logging.getLogger(__name__)


def backfill(graph: EntityGraph) -> dict[str, int]:
    rows = graph.query(
        "MATCH (m:Money) WHERE m.attributes IS NOT NULL "
        "RETURN m.id AS id, m.attributes AS a"
    )
    pays = 0
    owed = 0
    costed_to_brand = 0
    for r in rows:
        try:
            a = json.loads(r["a"])
        except Exception:
            continue
        if not isinstance(a, dict):
            continue
        vendor_id = a.get("vendor_id")
        client_id = a.get("client_id")
        if vendor_id:
            graph.conn.execute(
                "MATCH (m:Money), (o:Organisation) "
                "WHERE m.id = $m AND o.id = $o "
                "MERGE (m)-[:PAYS]->(o)",
                {"m": r["id"], "o": vendor_id},
            )
            pays += 1
        if client_id:
            graph.conn.execute(
                "MATCH (m:Money), (o:Organisation) "
                "WHERE m.id = $m AND o.id = $o "
                "MERGE (m)-[:OWED_BY]->(o)",
                {"m": r["id"], "o": client_id},
            )
            owed += 1
        brand_id = a.get("brand_id")
        if brand_id:
            graph.conn.execute(
                "MATCH (m:Money), (b:Brand) WHERE m.id = $m AND b.id = $b "
                "MERGE (m)-[:COSTED_TO_BRAND]->(b)",
                {"m": r["id"], "b": brand_id},
            )
            costed_to_brand += 1
    log.info("backfill: pays=%d owed_by=%d costed_to_brand=%d", pays, owed, costed_to_brand)
    return {"pays": pays, "owed_by": owed, "costed_to_brand": costed_to_brand}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--kuzu", default=os.getenv("PORTAL_DATA_DIR", "data/portal") + "/entity_graph.kuzu")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO)
    g = EntityGraph(Path(args.kuzu))
    summary = backfill(g)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
