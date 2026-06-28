"""Evaluation Runner.

Loads golden_set.json, dispatches to agents, applies check functions,
and prints a scoreboard.
"""

import json
import sys
from pathlib import Path
from decimal import Decimal

# Make the repo root importable so `python evals/run_eval.py` works from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.mentor import Mentor
from src.agents.board import convene_board
from src.agents.signal_agent import scan as scan_signals
from src.agents.orchestrator import Orchestrator

from src.eval.checks import (
    contains_exact_number,
    verdict_rejects,
    sizes_within_cap,
    routed_to
)

def run_evals():
    golden_path = Path(__file__).parent / "golden_set.json"
    if not golden_path.exists():
        print(f"Error: {golden_path} not found.")
        sys.exit(1)
        
    with open(golden_path, "r", encoding="utf-8") as f:
        cases = json.load(f)
        
    results = {
        "faithfulness": {"pass": 0, "total": 0},
        "rejects": {"pass": 0, "total": 0},
        "cap": {"pass": 0, "total": 0},
        "routing": {"pass": 0, "total": 0},
    }
    
    print("Running evaluation suite...\n")
    
    # Pre-instantiate agents that can be reused
    mentor = Mentor()
    orchestrator = Orchestrator()
    
    for case in cases:
        c_id = case["id"]
        agent_type = case["agent"]
        user_input = case["input"]
        check = case["check"]
        expected = case.get("expected")
        
        print(f"Running {c_id}...")
        passed = False
        
        try:
            if agent_type == "mentor":
                resp = mentor.ask(user_input)
                if check == "faithfulness":
                    passed = contains_exact_number(resp.answer, str(expected))
                    results["faithfulness"]["total"] += 1
                    if passed: results["faithfulness"]["pass"] += 1
                    
            elif agent_type == "board":
                ruling = convene_board(user_input)
                if check == "rejects":
                    passed = verdict_rejects(ruling.verdict)
                    results["rejects"]["total"] += 1
                    if passed: results["rejects"]["pass"] += 1
                    
            elif agent_type == "signal":
                watchlist = user_input["watchlist"]
                windfall = Decimal(str(user_input["windfall"]))
                signals = scan_signals(watchlist, windfall)
                if check == "cap":
                    passed = sizes_within_cap(signals, float(expected))
                    results["cap"]["total"] += 1
                    if passed: results["cap"]["pass"] += 1
                    
            elif agent_type == "orchestrator":
                res = orchestrator.run(user_input)
                if check.startswith("routes:"):
                    expected_tool = check.split(":")[1]
                    passed = routed_to(res, expected_tool)
                    results["routing"]["total"] += 1
                    if passed: results["routing"]["pass"] += 1
            
            print(f"  -> {'PASS' if passed else 'FAIL'}")
            
        except Exception as e:
            print(f"  -> ERROR: {e}")
            
    print("\n" + "=" * 40)
    print("  SCOREBOARD")
    print("=" * 40)
    
    total_passes = 0
    total_cases = 0
    for metric, stats in results.items():
        if stats["total"] > 0:
            rate = stats["pass"] / stats["total"]
            print(f"{metric.capitalize():15}: {stats['pass']}/{stats['total']} ({rate:.0%})")
            total_passes += stats["pass"]
            total_cases += stats["total"]
            
    print("-" * 40)
    overall = total_passes / total_cases if total_cases > 0 else 0
    print(f"OVERALL        : {total_passes}/{total_cases} ({overall:.0%})")
    print("=" * 40)
    
    if overall < 0.8:
        sys.exit(1)
        
if __name__ == "__main__":
    # Force UTF-8 output
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    
    run_evals()
