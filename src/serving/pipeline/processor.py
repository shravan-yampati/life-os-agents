"""Document processor — routes and processes documents from GCS.

Implements the two-path hybrid memory system:
- Financial Path: CSV/PDF statements -> transactions -> structured logging.
- Semantic Path: General documents -> chunking -> Vertex AI embeddings -> Vector store.
"""

import os
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.serving.pipeline.gcs_helper import download_file
from src.finance.statements import load_transactions
from src.finance.categorize import categorize
from src.ingestion.chunker import chunk_text
from src.ingestion.loader import load_document
from src.providers.factory import ProviderFactory
from src.retrieval.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def ingest_semantic_document(local_path: str, source_name: str) -> int:
    """Chunks, embeds, and stores a document in the vector store.

    Args:
        local_path: Path to the local file.
        source_name: Original file source identifier (e.g. GCS URI).

    Returns:
        Number of chunks stored.
    """
    text = load_document(local_path)
    chunks = chunk_text(text)
    if not chunks:
        logger.warning(f"No chunks extracted from {source_name}")
        return 0

    embeddings = ProviderFactory.get_embeddings()
    # Query a single token to determine the dimension of the embedding model
    probe = embeddings.embed_query("dimension probe")
    store = get_vector_store(dim=len(probe))

    vectors = embeddings.embed_documents(chunks)
    return store.add(chunks, vectors, source=source_name)


def process_document(bucket_name: str, file_name: str) -> dict:
    """Downloads a file from GCS and routes it based on its type/name.

    Args:
        bucket_name: GCS bucket containing the file.
        file_name: Path within the bucket.

    Returns:
        Metadata about the processing result.
    """
    local_path = None
    original_source = f"gs://{bucket_name}/{file_name}"
    logger.info(f"Processing document from {original_source}")

    try:
        # Step 1: Download file locally
        local_path = download_file(bucket_name, file_name)
        _, ext = os.path.splitext(file_name)
        ext = ext.lower()

        # Step 2: Determine if this is a financial statement
        is_financial = False
        name_lower = file_name.lower()
        if "finance" in name_lower or "statement" in name_lower or "transaction" in name_lower:
            is_financial = ext in (".csv", ".pdf")

        # Step 3: Route document accordingly
        if is_financial:
            logger.info(f"Routing {file_name} to FINANCIAL path")
            raw_txns = load_transactions(local_path)
            categorized_txns = categorize(raw_txns)
            
            # Print parsed transactions info to logs (temporary, will write to DB in Phase 2)
            total_spend = sum(t.amount for t in categorized_txns if t.is_spend)
            total_income = sum(t.amount for t in categorized_txns if t.is_income)
            logger.info(
                f"Financial processing complete: parsed {len(categorized_txns)} transactions. "
                f"Income: {total_income}, Spend: {total_spend}"
            )
            
            return {
                "file_name": file_name,
                "bucket": bucket_name,
                "type": "financial",
                "transaction_count": len(categorized_txns),
                "total_income": str(total_income),
                "total_spend": str(total_spend),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "status": "success"
            }
        else:
            logger.info(f"Routing {file_name} to SEMANTIC RAG path")
            chunk_count = ingest_semantic_document(local_path, original_source)
            logger.info(f"Semantic processing complete: stored {chunk_count} chunks.")
            
            return {
                "file_name": file_name,
                "bucket": bucket_name,
                "type": "semantic",
                "chunk_count": chunk_count,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "status": "success"
            }

    except Exception as e:
        logger.error(f"Processing failed for {file_name}: {e}", exc_info=True)
        return {
            "file_name": file_name,
            "bucket": bucket_name,
            "type": "unknown",
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "status": f"error: {e}"
        }

    finally:
        # Clean up temp file
        if local_path and os.path.exists(local_path):
            try:
                os.unlink(local_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {local_path}: {e}")
