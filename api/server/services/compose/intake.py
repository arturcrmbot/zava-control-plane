"""Normalize an uploaded document (or pasted text) into plain text for the
composition prompt. Fail soft: on any extractor error, fall back to a utf-8
decode so the agent still receives *something* to read.
"""
from __future__ import annotations

import io


def _extract_pdf(raw: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _extract_docx(raw: bytes) -> str:
    import docx  # python-docx
    document = docx.Document(io.BytesIO(raw))
    return "\n".join(p.text for p in document.paragraphs)


def extract_text(filename: str, raw: bytes) -> str:
    ext = ""
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
    try:
        if ext == "pdf":
            return _extract_pdf(raw)
        if ext == "docx":
            return _extract_docx(raw)
    except Exception:
        pass  # fall through to decode
    return raw.decode("utf-8", "ignore")
