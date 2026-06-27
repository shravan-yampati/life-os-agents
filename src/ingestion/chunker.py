"""Paragraph-aware text chunking with overlap."""

import re
from typing import List


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 150,
) -> List[str]:
    """Splits text into chunks of roughly chunk_size characters.

    Paragraph boundaries are respected where possible: paragraphs are
    packed into chunks until the size budget is exceeded. A paragraph
    longer than chunk_size is split on sentence boundaries with a
    character overlap between consecutive pieces.

    Args:
        text: The input document text.
        chunk_size: Soft maximum chunk length in characters.
        overlap: Characters of overlap when splitting long paragraphs.

    Returns:
        A list of non-empty chunk strings.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be in [0, chunk_size)")

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks: List[str] = []
    current = ""
    for para in paragraphs:
        if len(para) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_paragraph(para, chunk_size, overlap))
            continue
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) > chunk_size and current:
            chunks.append(current)
            current = para
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _split_long_paragraph(para: str, chunk_size: int, overlap: int) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+", para)
    pieces: List[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > chunk_size and current:
            pieces.append(current)
            # Carry a tail of the previous piece forward as overlap context
            tail = current[-overlap:] if overlap else ""
            current = f"{tail} {sentence}".strip() if tail else sentence
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces
