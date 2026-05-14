"""scripts/backfill_workflow_periods.py — Phase 4 Task 4.5.

For each Workflow node, find the Period whose [starts, ends] range contains
Workflow.started_at, then MERGE a WORKFLOW_IN_PERIOD edge.

Usage:
    python -m scripts.backfill_workflow_periods --kuzu data/portal/entity_graph.kuzu
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
        """
        MATCH (w:Workflow), (p:Period)
        WHERE w.started_at IS NOT NULL
          AND p.`starts` IS NOT NULL AND p.`ends` IS NOT NULL
          AND w.started_at >= p.`starts` AND w.started_at <= p.`ends`
        RETURN w.id AS wid, p.id AS pid
        """
    )
    n = 0
    for r in rows:
        graph.conn.execute(
            "MATCH (w:Workflow), (p:Period) "
            "WHERE w.id = $w AND p.id = $p "
            "MERGE (w)-[:WORKFLOW_IN_PERIOD]->(p)",
            {"w": r["wid"], "p": r["pid"]},
        )
        n += 1
    log.info("backfill_workflow_periods: workflow_in_period=%d", n)
    return {"workflow_in_period": n}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--kuzu",
        default=os.getenv("PORTAL_DATA_DIR", "data/portal") + "/entity_graph.kuzu",
    )
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO)
    g = EntityGraph(Path(args.kuzu))
    summary = backfill(g)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
