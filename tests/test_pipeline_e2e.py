"""End-to-end test of the naive RAG pipeline using the local provider
and the local vector store. No network, credentials, or database needed."""

import pytest

from src.config import settings
from src.retrieval.naive import NaiveRAG

DOC = """# Test Fund Facts

## Fees

The fund charges an annual expense ratio of 0.72 percent. The minimum
initial investment is 5,000 dollars for individual accounts.

## Management

The fund is managed by lead portfolio manager Sofia Reinhart, supported
by co-manager Daniel Okafor.

## Distributions

Dividends are distributed annually in December.
"""


@pytest.fixture()
def rag(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "local")
    monkeypatch.setattr(settings, "VECTOR_BACKEND", "local")
    monkeypatch.setattr(
        settings, "LOCAL_VECTOR_PATH", str(tmp_path / "store.json")
    )
    doc_path = tmp_path / "fund.md"
    doc_path.write_text(DOC, encoding="utf-8")
    pipeline = NaiveRAG(top_k=2)
    pipeline.ingest(doc_path)
    return pipeline


def test_ingest_stores_chunks(rag):
    assert rag.store.count() > 0


def test_ask_returns_grounded_answer(rag):
    response = rag.ask("What is the expense ratio of the fund?")
    assert "0.72" in response.answer
    assert response.sources
    assert any("expense ratio" in s.text for s in response.sources)


def test_ask_about_manager(rag):
    response = rag.ask("Who is the lead portfolio manager?")
    assert "Sofia Reinhart" in response.answer


def test_ask_empty_store(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "local")
    monkeypatch.setattr(settings, "VECTOR_BACKEND", "local")
    monkeypatch.setattr(
        settings, "LOCAL_VECTOR_PATH", str(tmp_path / "empty.json")
    )
    pipeline = NaiveRAG()
    response = pipeline.ask("Anything?")
    assert "No documents" in response.answer
