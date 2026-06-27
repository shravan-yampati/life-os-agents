"""Tests for PDF support in the RAG document loader (the drop-zone path).

Verifies a life-document PDF (e.g. an education certificate) is read as text
and is answerable through the NaiveRAG pipeline end-to-end.
"""

import pytest

from src.config import settings
from src.ingestion.loader import load_document
from src.retrieval.naive import NaiveRAG

CERT_LINES = [
    "UNIVERSITY OF EXAMPLE",
    "Certificate of Degree",
    "",
    "This certifies that Shravan Reddy Yampati has been awarded the degree of",
    "Master of Science in Computer Science",
    "conferred on June 15, 2015, with a cumulative GPA of 3.8.",
    "",
    "Registrar: Dr. Jane Smith",
]


def _make_cert_pdf(path):
    pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    text = c.beginText(40, 720)
    for line in CERT_LINES:
        text.textLine(line)
    c.drawText(text)
    c.save()
    return path


def test_load_document_reads_pdf_text(tmp_path):
    pdf = _make_cert_pdf(tmp_path / "cert.pdf")
    content = load_document(pdf)
    assert "Master of Science in Computer Science" in content
    assert "University of Example".upper() in content.upper()


def test_load_document_rejects_unsupported(tmp_path):
    p = tmp_path / "thing.xyz"
    p.write_text("data", encoding="utf-8")
    with pytest.raises(ValueError):
        load_document(p)


def test_certificate_pdf_answerable_via_rag(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "local")
    monkeypatch.setattr(settings, "VECTOR_BACKEND", "local")
    monkeypatch.setattr(settings, "LOCAL_VECTOR_PATH", str(tmp_path / "store.json"))

    pdf = _make_cert_pdf(tmp_path / "cert.pdf")
    rag = NaiveRAG(top_k=2)
    assert rag.ingest(pdf) > 0

    response = rag.ask("What degree was awarded and in what field?")
    assert "Master of Science in Computer Science" in response.answer
    assert response.sources
