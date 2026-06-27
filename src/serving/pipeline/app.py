"""FastAPI application — the Cloud Run entry point.

Receives Pub/Sub push messages, decodes GCS file info, and triggers document
processing and routing.
"""

import os
import json
import base64
import logging
from fastapi import FastAPI, Request, Response, status
from pydantic import BaseModel

from src.serving.pipeline.processor import process_document

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RAG-Lab Cloud Run Ingestion Pipeline")


class PubSubMessage(BaseModel):
    """Pydantic model representing the Pub/Sub envelope message field."""
    data: str
    messageId: str
    publishTime: str


class PubSubEnvelope(BaseModel):
    """Pydantic model representing the outer Pub/Sub message envelope."""
    message: PubSubMessage


@app.get("/")
def health():
    """Health check endpoint — Cloud Run pings this to confirm the service is alive."""
    return {"status": "healthy", "service": "gcs-pipeline"}


@app.post("/process")
async def handle_pubsub(envelope: PubSubEnvelope, response: Response):
    """Receives a Pub/Sub push message triggered by a GCS file upload.

    Decodes the GCS file details from the Pub/Sub envelope, downloads the
    file, and routes it to the correct RAG or financial processing path.
    """
    try:
        # Step 1: Decode the base64 GCS notification payload
        decoded_data = base64.b64decode(envelope.message.data).decode("utf-8")
        data = json.loads(decoded_data)
    except Exception as e:
        logger.error(f"Failed to decode Pub/Sub envelope data: {e}")
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": f"Bad Request: Failed to decode base64 data - {e}"}

    bucket_name = data.get("bucket")
    file_name = data.get("name")

    if not bucket_name or not file_name:
        logger.warning(f"Missing bucket or file name in payload: {data}")
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "Bad Request: Missing bucket or file name"}

    logger.info(f"Triggered processing for: gs://{bucket_name}/{file_name}")

    # Step 2: Route and process the document
    result = process_document(bucket_name, file_name)

    if result.get("status", "").startswith("error"):
        logger.error(f"Processing encountered an error for {file_name}: {result['status']}")
        # Return HTTP 200 anyway to prevent Pub/Sub from retrying broken documents forever
        return {
            "status": "acknowledged_error",
            "message": "Processing failed but message acknowledged to prevent infinite Pub/Sub retries.",
            "detail": result
        }

    return {"status": "success", "result": result}
