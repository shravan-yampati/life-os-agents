"""GCS helper — downloads files from Google Cloud Storage.

This module is responsible for connecting to GCS and downloading the uploaded
file to a temporary file locally so it can be parsed and routed by the processor.
"""

import os
import tempfile
import logging
from google.cloud import storage

from src.config import settings

logger = logging.getLogger(__name__)

# Lazy-initialized client (matches the pattern in src/providers/gcp.py)
_client = None


def _get_client():
    """Returns a lazily-initialized GCS client."""
    global _client
    if _client is None:
        _client = storage.Client(project=settings.GCP_PROJECT_ID)
    return _client


def download_file(bucket_name: str, file_name: str) -> str:
    """Downloads a file from GCS to a local temporary path.

    Args:
        bucket_name: The GCS bucket name (e.g. 'rag-lab-pipeline-bucket')
        file_name: The object path in the bucket (e.g. 'uploads/doc.pdf')

    Returns:
        Local filesystem path to the downloaded temp file.
    """
    try:
        bucket = _get_client().bucket(bucket_name)
        blob = bucket.blob(file_name)

        # Create temp file with the same extension so our parsers recognize the type
        _, ext = os.path.splitext(file_name)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        tmp.close()

        blob.download_to_filename(tmp.name)
        logger.info(f"Downloaded gs://{bucket_name}/{file_name} → {tmp.name}")
        return tmp.name

    except Exception as exc:
        raise RuntimeError(
            f"Failed to download gs://{bucket_name}/{file_name}: {exc}"
        ) from exc
