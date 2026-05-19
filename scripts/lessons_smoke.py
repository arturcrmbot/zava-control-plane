"""End-to-end smoke for the lesson store foundation (B1).

Writes a lesson through LessonGovernor (which exercises AGT eval +
Kuzu provenance + the audit ledger), reads it back via search,
prunes it, and dumps the resulting ledger entries so you can eyeball
the chain.

Uses InMemoryLessonStore so it requires no Mem0 server. For the real
mem0 backend, swap to Mem0LessonStore — see
tests/api/services/lessons/test_mem0_store_integration.py for the
Azure OpenAI keyless config.

Usage:
    uv run python scripts/lessons_smoke.py
"""
from __future__ import annotations

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from api.server.services.audit_logger import AuditLogger
from api.server.services.entity_graph import EntityGraph
from api.server.services.governance.kernel import kernel
from api.server.services.lessons import (
    InMemoryLessonStore,
    KuzuLessonProvenance,
    Lesson,
    LessonGovernor,
    LessonProvenance,
    LessonScope,
)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="lessons-smoke-"))
    graph = EntityGraph(str(tmp / "smoke.kuzu"))

    run_id = "WF-SMOKE-001"
    graph.query(
        "CREATE (:Workflow {id: $id, workflow_type: 'hiring', status: 'complete'})",
        {"id": run_id},
    )

    store = InMemoryLessonStore()
    provenance = KuzuLessonProvenance(graph)
    audit = AuditLogger()
    governor = LessonGovernor(
        store=store,
        kernel=kernel,
        audit=audit,
        provenance=provenance,
        actor="dream-pass:hiring:smoke",
    )

    lesson = Lesson(
        id=str(uuid.uuid4()),
        body="vendors from agency X often miss reference checks at step 3",
        scope=LessonScope(domain="hiring"),
        provenance=LessonProvenance(
            proposed_by="dream-pass:hiring:smoke",
            run_ids=(run_id,),
            rubric_score_delta=0.08,
            experiment_n=40,
            promoted_at=datetime.now(timezone.utc),
        ),
    )

    print(f"writing lesson {lesson.id} ...")
    governor.write(lesson)
    print(f"  scope={lesson.scope}")
    print(f"  delta={lesson.provenance.rubric_score_delta} n={lesson.provenance.experiment_n}")

    found = store.search("reference checks", scope=lesson.scope, top_k=5)
    print(f"search returned {len(found)} lesson(s); ids={[lesson_.id for lesson_ in found]}")

    print(f"pruning lesson {lesson.id} ...")
    governor.prune(lesson.id, reason="smoke run complete")

    after = store.search("reference checks", scope=lesson.scope, top_k=5)
    print(f"search after prune: {len(after)} (expected 0)")

    rows = graph.query(
        "MATCH (l:Lesson {id: $id}) RETURN l.status AS status, l.prune_reason AS reason",
        {"id": lesson.id},
    )
    print(f"kuzu lesson row: {rows}")

    print()
    print("--- audit ledger entries ---")
    for entry in audit.list():
        print(
            f"  action={entry['action']:<14} "
            f"decision_id={entry['details'].get('decision_id', '?')[:8]}.. "
            f"gov={entry['details'].get('governance_action')} "
            f"entry_hash={entry['entry_hash'][:8]}.."
        )

    graph.close()
    print()
    print("smoke ok")


if __name__ == "__main__":
    main()
