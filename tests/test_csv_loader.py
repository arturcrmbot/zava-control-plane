from pathlib import Path
from helpers.csv_loader import load_answer_csvs, AnswerRow


def test_load_answer_csvs_joins_multiple_files(fixtures_dir):
    rows = load_answer_csvs(fixtures_dir / "mini-answers")
    assert len(rows) == 3
    refs = [r.ref for r in rows]
    assert refs == ["1.1", "1.2", "2.1"]  # sorted natural order


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


def test_natural_ref_sort(fixtures_dir):
    # Ensure 10.1 sorts AFTER 2.x, not between 1.x and 2.x
    rows = load_answer_csvs(fixtures_dir / "mini-answers")
    assert rows == sorted(rows, key=lambda r: tuple(int(p) for p in r.ref.split(".")))
