from api.server.services.compose import intake


def test_plaintext_passthrough():
    assert intake.extract_text("note.txt", b"hello world") == "hello world"


def test_markdown_passthrough():
    assert intake.extract_text("spec.md", b"# Title\nbody") == "# Title\nbody"


def test_unknown_extension_decodes_utf8():
    assert intake.extract_text("blob", b"raw text") == "raw text"


def test_pdf_dispatches_to_pdf_extractor(monkeypatch):
    monkeypatch.setattr(intake, "_extract_pdf", lambda raw: "PDF TEXT")
    assert intake.extract_text("doc.PDF", b"%PDF-1.4...") == "PDF TEXT"


def test_docx_dispatches_to_docx_extractor(monkeypatch):
    monkeypatch.setattr(intake, "_extract_docx", lambda raw: "DOCX TEXT")
    assert intake.extract_text("doc.docx", b"PK...") == "DOCX TEXT"


def test_extractor_failure_falls_back_to_decode(monkeypatch):
    def boom(raw):
        raise ValueError("bad pdf")
    monkeypatch.setattr(intake, "_extract_pdf", boom)
    assert intake.extract_text("doc.pdf", b"fallbacktext") == "fallbacktext"
