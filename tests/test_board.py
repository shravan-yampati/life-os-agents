"""Board of Directors — structural test, offline (uses the local provider so no
network/API key is needed). Verifies the debate fans out to every persona and the
Synthesizer produces a ruling."""

from src.config import settings
from src.agents.board import PERSONAS, Ruling, convene_board


def test_board_runs_offline(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "local")
    foundation = tmp_path / "foundation.md"
    foundation.write_text(
        "Goal: save $80K by 2027. Non-negotiable: no new bad debt; keep an "
        "emergency fund. Risk: barbell, clever not YOLO.",
        encoding="utf-8",
    )

    ruling = convene_board("Should I take a $20,000 loan for a vacation?", foundation)

    assert isinstance(ruling, Ruling)
    assert len(ruling.opinions) == len(PERSONAS)          # all four advisors weighed in
    assert {o.persona for o in ruling.opinions} == set(PERSONAS)
    assert all(o.text.strip() for o in ruling.opinions)   # nobody returned empty
    assert ruling.verdict.strip()                         # synthesizer ruled


def test_missing_foundation_is_handled(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CLOUD_PROVIDER", "local")
    ruling = convene_board("Anything?", tmp_path / "does_not_exist.md")
    assert len(ruling.opinions) == len(PERSONAS)
