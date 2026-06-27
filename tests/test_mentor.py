"""Mentor — offline structural test (local provider, no network/API key)."""

from src.agents.mentor import Mentor, MentorResponse
from src.config import settings


def test_mentor_grounds_on_exact_numbers(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "local")
    resp = Mentor(person="me").ask("How am I doing on savings?")
    assert isinstance(resp, MentorResponse)
    assert resp.answer.strip()
    # The exact-facts block must carry real computed numbers (not guessed).
    assert "Total income" in resp.facts_used
    assert "savings rate" in resp.facts_used


def test_mentor_handles_missing_statement(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "local")
    resp = Mentor().ask("Anything?", statement_path=tmp_path / "nope.csv")
    assert "No statement loaded" in resp.facts_used
    assert resp.answer.strip()
