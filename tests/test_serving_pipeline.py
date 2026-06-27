"""Unit tests for the FastAPI Cloud Run ingestion pipeline.

Verifies URL routing, Pub/Sub decoding, and the two-path document router.
Runs entirely offline using the local provider and local vector store.
"""

import base64
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from src.config import settings
from src.serving.pipeline.app import app
from src.retrieval.vector_store import get_vector_store

client = TestClient(app)

# Mock semantic document content
SEMANTIC_DOC = """# Technical Spec
This is a technical document about building AI agents.
It discusses LangGraph, FastAPI, and pgvector.
"""

# Mock financial statement CSV content
FINANCIAL_CSV = """Date,Description,Amount
2026-06-15,Starbucks,-4.50
2026-06-15,Google Payroll,3500.00
2026-06-15,Comcast,-80.00
"""


@pytest.fixture(autouse=True)
def setup_local_test_env(tmp_path, monkeypatch):
    """Enforces offline local backends for all pipeline tests."""
    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "local")
    monkeypatch.setattr(settings, "VECTOR_BACKEND", "local")
    monkeypatch.setattr(
        settings, "LOCAL_VECTOR_PATH", str(tmp_path / "test_store.json")
    )


def test_health_check():
    """Verifies that the GET / endpoint is healthy."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "gcs-pipeline"}


def test_process_invalid_envelope():
    """Verifies that bad Pub/Sub envelopes return 400 Bad Request."""
    response = client.post("/process", json={"bad_key": "bad_value"})
    assert response.status_code == 422  # Pydantic validation error code (Unprocessable Entity)

    # Let's send a valid envelope structure but with un-decodable base64 data
    response = client.post(
        "/process",
        json={
            "message": {
                "data": "not-valid-base64!!!",
                "messageId": "123",
                "publishTime": "2026-06-15T00:00:00Z"
            }
        }
    )
    assert response.status_code == 400
    assert "Failed to decode base64 data" in response.json()["error"]


@patch("src.serving.pipeline.processor.download_file")
def test_process_semantic_document(mock_download, tmp_path):
    """Verifies semantic document routing, chunking, and embedding."""
    # Setup mock download to return a temp file with our test doc
    temp_file = tmp_path / "spec.md"
    temp_file.write_text(SEMANTIC_DOC, encoding="utf-8")
    mock_download.return_value = str(temp_file)

    # Build the Pub/Sub push envelope payload
    gcs_notification = {"bucket": "test-bucket", "name": "docs/spec.md"}
    encoded_data = base64.b64encode(json.dumps(gcs_notification).encode("utf-8")).decode("utf-8")

    payload = {
        "message": {
            "data": encoded_data,
            "messageId": "msg-001",
            "publishTime": "2026-06-15T00:00:00Z"
        }
    }

    # Clear vector store before run
    store = get_vector_store(dim=1)  # local store doesn't enforce dimension
    store.clear()

    response = client.post("/process", json=payload)
    assert response.status_code == 200
    res_data = response.json()

    assert res_data["status"] == "success"
    assert res_data["result"]["type"] == "semantic"
    assert res_data["result"]["chunk_count"] > 0
    
    # Instantiate a fresh store after the API call to read the written JSON file
    after_store = get_vector_store(dim=1)
    assert after_store.count() > 0


@patch("src.serving.pipeline.processor.download_file")
def test_process_financial_document(mock_download, tmp_path):
    """Verifies financial statement routing and transaction parsing."""
    # Setup mock download to return a temp file with our test CSV
    temp_file = tmp_path / "finance_statement.csv"
    temp_file.write_text(FINANCIAL_CSV, encoding="utf-8")
    mock_download.return_value = str(temp_file)

    # Build the Pub/Sub push envelope payload
    gcs_notification = {"bucket": "test-bucket", "name": "statements/finance_statement.csv"}
    encoded_data = base64.b64encode(json.dumps(gcs_notification).encode("utf-8")).decode("utf-8")

    payload = {
        "message": {
            "data": encoded_data,
            "messageId": "msg-002",
            "publishTime": "2026-06-15T00:00:00Z"
        }
    }

    response = client.post("/process", json=payload)
    assert response.status_code == 200
    res_data = response.json()

    assert res_data["status"] == "success"
    assert res_data["result"]["type"] == "financial"
    assert res_data["result"]["transaction_count"] == 3
    assert res_data["result"]["total_income"] == "3500.00"
    assert res_data["result"]["total_spend"] == "-84.50"
