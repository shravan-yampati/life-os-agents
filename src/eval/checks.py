"""Evaluation check functions.

These are pure, deterministic functions that evaluate agent outputs without requiring an LLM.
"""

from decimal import Decimal
from typing import List, Any
import re
from src.agents.orchestrator import OrchestratorResult


def contains_exact_number(answer: str, value: str) -> bool:
    """Check if the generated answer contains the required exact metric."""
    return str(value) in answer


def verdict_rejects(verdict: str) -> bool:
    """Check if the Board of Directors synthesizer rejected the decision.
    
    Looks for clear rejection signals like "No", "Wait", "reject", etc.
    It expects the verdict to start with "1. VERDICT: No" or similar.
    """
    verdict_lower = verdict.lower()
    
    # Try to find the verdict line specifically
    match = re.search(r'verdict:\s*([^\n]*)', verdict_lower)
    if match:
        v_line = match.group(1)
        # Often the format is "1. VERDICT: No" or "1. VERDICT: Wait"
        if "no" in v_line or "wait" in v_line or "reject" in v_line:
            return True
            
    # Fallback to general text check if the formatting isn't perfect
    if "verdict: no" in verdict_lower or "verdict: wait" in verdict_lower:
        return True
        
    return False


def sizes_within_cap(signals: List[Any], cap: float) -> bool:
    """Verify that the Signal Agent respected the windfall cap for every suggested trade."""
    # If there are no signals, it didn't violate the cap.
    if not signals:
        return True
    
    cap_decimal = Decimal(str(cap))
    for signal in signals:
        if getattr(signal, "suggested_size_usd", Decimal("0")) > cap_decimal:
            return False
            
    return True


def routed_to(result: OrchestratorResult, expected_tool: str) -> bool:
    """Verify the Orchestrator chose the expected tool."""
    return result.tool_used == expected_tool
