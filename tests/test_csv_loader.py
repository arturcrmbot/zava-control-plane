from pathlib import Path
import pytest
from helpers.csv_loader import load_answer_csvs, AnswerRow


def test_load_answer_csvs_joins_multiple_files(fixtures_dir):
    rows = load_answer_csvs(fixtures_dir / "mini-answers")
    assert len(rows) == 4
    refs = [r.ref for r in rows]
    assert refs == ["1.1", "1.2", "2.1", "10.1"]  # sorted natural order


def test_answer_row_shape(fixtures_dir):
    rows = load_answer_csvs(fixtures_dir / "mini-answers")
    r = rows[0]
    assert isinstance(r, AnswerRow)
    assert r.ref == "1.1"
    assert r.section == "Test Section"
    assert r.subsection == "Test Sub"
    assert r.question == "Test question one"
    assert r.moscow == "Must"
    assert r.status == "Can do today"
    assert r.response == "Test response one"
    assert r.key_technologies == "Tech A"
    assert r.poc_demo == "Demo one"
    assert r.reference == "https://example.com"


def test_natural_ref_sort_10_after_2(fixtures_dir):
    rows = load_answer_csvs(fixtures_dir / "mini-answers")
    # Natural sort: 10.1 must come AFTER 2.1, not between 1.x and 2.x (which would be lexicographic)
    refs = [r.ref for r in rows]
    assert refs.index("10.1") > refs.index("2.1"), f"Natural sort failed: {refs}"


def test_missing_column_raises(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("Ref,Section\n1.1,X\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_answer_csvs(tmp_path)
