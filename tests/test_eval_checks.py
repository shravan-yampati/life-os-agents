import pytest
from decimal import Decimal
from src.eval.checks import (
    contains_exact_number,
    verdict_rejects,
    sizes_within_cap,
    routed_to
)
from src.agents.orchestrator import OrchestratorResult

def test_contains_exact_number():
    assert contains_exact_number("The safe to spend is 142.50.", "142.50")
    assert not contains_exact_number("The safe to spend is 142.", "142.50")
    assert contains_exact_number("You have 500 dollars", 500)

def test_verdict_rejects():
    assert verdict_rejects("1. VERDICT: No, do not do this.\n2. WHY: Bad idea.")
    assert verdict_rejects("1. VERDICT: Wait\n2. WHY: Not yet.")
    assert verdict_rejects("1. VERDICT: Reject\n")
    assert not verdict_rejects("1. VERDICT: Yes\n2. WHY: Great idea.")
    assert not verdict_rejects("1. VERDICT: Yes-but\n2. WHY: Be careful.")

def test_sizes_within_cap():
    class DummySignal:
        def __init__(self, size):
            self.suggested_size_usd = Decimal(str(size))
            
    assert sizes_within_cap([DummySignal(100), DummySignal(200)], 300.0)
    assert sizes_within_cap([DummySignal(300)], 300.0)
    assert not sizes_within_cap([DummySignal(301)], 300.0)
    assert not sizes_within_cap([DummySignal(100), DummySignal(500)], 300.0)
    assert sizes_within_cap([], 300.0)

def test_routed_to():
    res1 = OrchestratorResult(tool_used="ask_mentor", args={}, output="")
    assert routed_to(res1, "ask_mentor")
    assert not routed_to(res1, "convene_board")
