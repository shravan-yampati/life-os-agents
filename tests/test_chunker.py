import pytest

from src.ingestion.chunker import chunk_text


def test_short_text_single_chunk():
    assert chunk_text("Hello world.") == ["Hello world."]


def test_paragraphs_packed_within_budget():
    text = "Para one.\n\nPara two.\n\nPara three."
    chunks = chunk_text(text, chunk_size=25, overlap=5)
    assert len(chunks) >= 2
    assert all(len(c) <= 25 for c in chunks)
    # No content lost
    assert "Para one." in chunks[0]
    assert any("Para three." in c for c in chunks)


def test_long_paragraph_split_with_overlap():
    sentence = "This is a fairly long sentence about funds. "
    text = sentence * 20
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 260 for c in chunks)  # size + carried overlap


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("\n\n\n") == []


def test_invalid_params_raise():
    with pytest.raises(ValueError):
        chunk_text("x", chunk_size=0)
    with pytest.raises(ValueError):
        chunk_text("x", chunk_size=100, overlap=100)
