"""Tests for the Signal Agent."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.config import settings
from src.agents.signal_agent import scan, Signal, log_signals, record_outcome


@pytest.fixture
def offline_mock(monkeypatch):
    """Forces the LLM provider to 'local' for offline tests."""
    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "local")


def test_scan_with_headlines_and_windfall_cap(offline_mock, tmp_path):
    """Test scan caps suggested size to windfall."""
    headlines_file = tmp_path / "headlines.json"
    headlines_file.write_text(json.dumps([{"title": "Test Catalyst"}]))
    
    foundation_path = tmp_path / "foundation.md"
    foundation_path.write_text("Test rules")

    # In local LLM mock, we need to ensure it returns valid JSON. 
    # Let's mock ProviderFactory.get_llm() instead of just CLOUD_PROVIDER 
    # to control the exact JSON returned.
    class MockLLM:
        def generate(self, prompt, **kwargs):
            return json.dumps([{
                "ticker": "AAPL",
                "catalyst": "New product",
                "play": "Calls",
                "conviction": "high",
                "suggested_size_usd": 500.0, # Deliberately higher than windfall
                "rationale": "Strong cycle"
            }])
            
    import src.agents.signal_agent
    original_get_llm = src.agents.signal_agent.ProviderFactory.get_llm
    src.agents.signal_agent.ProviderFactory.get_llm = lambda: MockLLM()
    
    try:
        signals = scan(["AAPL"], windfall_usd=Decimal("300"), headlines_file=headlines_file, foundation_path=foundation_path)
        assert len(signals) == 1
        sig = signals[0]
        assert sig.ticker == "AAPL"
        # Verify the windfall cap worked (suggested 500, but capped to 300)
        assert sig.suggested_size_usd == Decimal("300")
    finally:
        src.agents.signal_agent.ProviderFactory.get_llm = original_get_llm


def test_ledger_append_and_record(tmp_path):
    ledger = tmp_path / "signals.jsonl"
    
    sig = Signal(
        signal_id="123",
        ticker="MU",
        catalyst="Earnings",
        play="Calls",
        conviction="med",
        suggested_size_usd=Decimal("200"),
        rationale="Growth"
    )
    
    # Test Append
    log_signals([sig], ledger_path=ledger)
    assert ledger.exists()
    lines = ledger.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    d = json.loads(lines[0])
    assert d["signal_id"] == "123"
    assert d["status"] == "open"
    assert d["outcome"] is None
    
    # Test Record Outcome
    success = record_outcome("123", "win", Decimal("50.0"), ledger_path=ledger)
    assert success is True
    
    lines = ledger.read_text(encoding="utf-8").strip().split("\n")
    d = json.loads(lines[0])
    assert d["status"] == "closed"
    assert d["outcome"] == "win"
    assert d["pnl"] == 50.0
