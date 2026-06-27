"""Document loading for the ingestion (RAG) pipeline.

This is the entry point for the document DROP ZONE: life documents (education
certificates, records, notes) that the bot should be able to answer questions
about. It returns the document's full text, which the chunker + embeddings then
turn into searchable vector memory.

Note the difference from finance statement parsing: here a PDF is treated as a
body of text to understand, NOT as rows of transactions to compute on. Money
data comes from Plaid into the structured store; documents come here into the
vector store. Two halves of hybrid memory.
"""

from pathlib import Path

TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | {".pdf"}


def extract_text_from_pdf(path: str | Path) -> str:
    """Extracts all text from a text-based PDF, page by page.

    Handles digital ("text") PDFs such as downloaded certificates and reports.
    Scanned/image PDFs would need OCR (a later upgrade) and yield little here.

    Args:
        path: Path to the PDF.

    Returns:
        The concatenated text of all pages.
    """
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def load_document(path: str | Path) -> str:
    """Reads a document into plain text for the RAG pipeline.

    Args:
        path: Path to a .txt, .md, or .pdf document.

    Returns:
        The document contents as a string.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If the file extension is not supported.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    raise ValueError(
        f"Unsupported file type '{path.suffix}'. "
        f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
    )
