"""Tests for the ingestion tracker."""

import json
from pathlib import Path

import pytest

from src.ingestion.tracker import get_file_hash, ingest


def test_get_file_hash(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("Hello World!")
    
    hash1 = get_file_hash(f)
    assert len(hash1) == 64
    
    # Hash should be deterministic
    assert get_file_hash(f) == hash1
    
    f2 = tmp_path / "test2.txt"
    f2.write_text("Hello World!")
    assert get_file_hash(f2) == hash1


def test_ingest_and_deduplicate(tmp_path, monkeypatch):
    """Tests the full ingestion pipeline offline."""
    # Mock LLM to return 'bank_statement'
    class MockLLM:
        def generate(self, prompt, **kwargs):
            return "bank_statement"
            
    import src.ingestion.tracker
    monkeypatch.setattr(src.ingestion.tracker.ProviderFactory, "get_llm", lambda: MockLLM())
    
    source_file = tmp_path / "chase_stmt.pdf"
    source_file.write_text("fake pdf content")
    
    manifest_path = tmp_path / "manifest.json"
    data_dir = tmp_path / "data"
    
    # First Ingest
    res1 = ingest(source_file, manifest_path=manifest_path, data_dir=data_dir)
    assert res1["status"] == "success"
    assert "chase_stmt" in res1["manifest_entry"]["dest_path"]
    
    # Verify file was moved to the right folder
    finance_dir = data_dir / "finance"
    assert finance_dir.exists()
    files = list(finance_dir.glob("*.pdf"))
    assert len(files) == 1
    
    # Verify Manifest
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert res1["file_hash"] in manifest
    assert manifest[res1["file_hash"]]["type"] == "bank_statement"
    
    # Second Ingest (Duplicate)
    res2 = ingest(source_file, manifest_path=manifest_path, data_dir=data_dir)
    assert res2["status"] == "skipped"
    assert res2["reason"] == "duplicate"
    
    # Verify no new files were created
    files_after = list(finance_dir.glob("*.pdf"))
    assert len(files_after) == 1
