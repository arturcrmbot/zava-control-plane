from docx import Document
from helpers.docx_populate.placeholders import resolve_inline_placeholder, PlaceholderRule


def test_replace_placeholder_paragraph(tmp_path, fixtures_dir):
    doc = Document(fixtures_dir / "mini-master.docx")
    rule = PlaceholderRule(
        match_prefix="<<Fill me please>>",
        resolution="replace_with",
        content="This is the replacement content.",
    )
    found = resolve_inline_placeholder(doc, rule)
    assert found is True
    out = tmp_path / "out.docx"
    doc.save(out)
    reloaded = Document(out)
    texts = [p.text for p in reloaded.paragraphs]
    assert "<<Fill me please>>" not in " ".join(texts)
    assert any("This is the replacement content." in t for t in texts)


def test_delete_placeholder_paragraph(tmp_path, fixtures_dir):
    doc = Document(fixtures_dir / "mini-master.docx")
    rule = PlaceholderRule(
        match_prefix="Cut and paste below",
        resolution="delete_paragraph",
    )
    found = resolve_inline_placeholder(doc, rule)
    assert found is True
    out = tmp_path / "out.docx"
    doc.save(out)
    reloaded = Document(out)
    texts = [p.text for p in reloaded.paragraphs]
    assert not any("Cut and paste" in t for t in texts)


def test_missing_placeholder_returns_false(fixtures_dir):
    doc = Document(fixtures_dir / "mini-master.docx")
    rule = PlaceholderRule(
        match_prefix="<<Not actually in the doc>>",
        resolution="replace_with",
        content="irrelevant",
    )
    assert resolve_inline_placeholder(doc, rule) is False
