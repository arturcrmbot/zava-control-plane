from __future__ import annotations

import pytest

from api.server.services.entity_graph import EntityGraph
from api.server.services.lessons.kuzu_provenance import KuzuLessonProvenance


@pytest.fixture
def graph(tmp_path):
    db_path = str(tmp_path / "lessons.kuzu")
    g = EntityGraph(db_path)
    yield g
    g.close()


def _table_names(graph: EntityGraph) -> set[str]:
    rows = graph.query("CALL show_tables() RETURN name")
    return {row["name"] for row in rows}


def test_lesson_node_table_exists(graph) -> None:
    assert "Lesson" in _table_names(graph)


def test_lesson_from_run_rel_table_exists(graph) -> None:
    assert "LESSON_FROM_RUN" in _table_names(graph)


def test_record_lesson_inserts_node_and_run_edges(graph, make_lesson) -> None:
    lesson = make_lesson()
    for run_id in lesson.provenance.run_ids:
        graph.query(
            "CREATE (:Workflow {id: $id, workflow_type: 'hiring', status: 'complete'})",
            {"id": run_id},
        )

    provenance = KuzuLessonProvenance(graph)
    provenance.record(lesson)

    rows = graph.query(
        "MATCH (l:Lesson {id: $id}) RETURN l.body AS body, l.domain AS domain",
        {"id": lesson.id},
    )
    assert rows[0]["body"] == lesson.body
    assert rows[0]["domain"] == "hiring"

    edge_rows = graph.query(
        "MATCH (l:Lesson {id: $id})-[:LESSON_FROM_RUN]->(w:Workflow) RETURN w.id AS run_id",
        {"id": lesson.id},
    )
    assert {r["run_id"] for r in edge_rows} == set(lesson.provenance.run_ids)


def test_mark_pruned_updates_status(graph, make_lesson) -> None:
    lesson = make_lesson()
    for run_id in lesson.provenance.run_ids:
        graph.query(
            "CREATE (:Workflow {id: $id, workflow_type: 'hiring', status: 'complete'})",
            {"id": run_id},
        )
    provenance = KuzuLessonProvenance(graph)
    provenance.record(lesson)

    provenance.mark_pruned(lesson.id, reason="superseded")

    rows = graph.query(
        "MATCH (l:Lesson {id: $id}) RETURN l.status AS status, l.prune_reason AS reason",
        {"id": lesson.id},
    )
    assert rows[0]["status"] == "pruned"
    assert rows[0]["reason"] == "superseded"
