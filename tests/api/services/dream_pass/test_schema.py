from __future__ import annotations


def test_dream_pass_tables_exist(graph) -> None:
    rows = graph.query('CALL show_tables() RETURN name')
    names = {row['name'] for row in rows}
    assert 'DreamPass' in names
    assert 'Experiment' in names
    assert 'EXPERIMENT_FOR_LESSON' in names
    assert 'EXPERIMENT_USED_PERSONA' in names
