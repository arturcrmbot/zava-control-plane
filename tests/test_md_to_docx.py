from docx import Document
from helpers.docx_populate.md_to_docx import render_md_into_doc


def test_render_paragraphs_and_headings(tmp_path):
    doc = Document()
    md = """## Heading Two

A paragraph with **bold** and *italic*.

### Heading Three

- Bullet one
- Bullet two

Another paragraph.
"""
    render_md_into_doc(doc, md)
    out = tmp_path / "out.docx"
    doc.save(out)
    reloaded = Document(out)
    styles = [(p.style.name, p.text) for p in reloaded.paragraphs if p.text.strip()]
    assert styles[0][0].lower().startswith("heading")
    assert styles[0][1] == "Heading Two"
    assert any(p.text == "Bullet one" for p in reloaded.paragraphs)


def test_render_preserves_bold(tmp_path):
    doc = Document()
    md = "A **bold** word."
    render_md_into_doc(doc, md)
    para = doc.paragraphs[-1]
    runs = list(para.runs)
    assert any(r.bold and r.text == "bold" for r in runs)
