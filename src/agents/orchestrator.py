"""Orchestrator Router — The main entry point for the Life OS."""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable, Any, Dict

from src.agents.board import convene_board
from src.agents.mentor import Mentor
from src.agents.signal_agent import scan as scan_signals
from src.finance.analyze import analyze
from src.finance.categorize import categorize
from src.finance.safe_to_spend import safe_to_spend
from src.finance.statements import load_transactions
from src.providers.factory import ProviderFactory

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_STATEMENT = _REPO_ROOT / "data" / "finance" / "sample_transactions.csv"


@dataclass
class Tool:
    name: str
    description: str
    func: Callable
    arg_hint: str


@dataclass
class OrchestratorResult:
    tool_used: str
    args: dict
    output: Any


def _finance_summary_tool() -> str:
    if not _DEFAULT_STATEMENT.exists():
        return "No statement found to analyze."
    txns = categorize(load_transactions(_DEFAULT_STATEMENT))
    if not txns:
        return "No transactions found."
    summary = analyze(txns)
    return (
        f"Total Income: ${summary.total_income:,.2f}\n"
        f"Total Spend: ${summary.total_spend:,.2f}\n"
        f"Net: ${summary.net:,.2f}\n"
        f"Savings Rate: {summary.savings_rate}%"
    )


def _safe_to_spend_tool() -> str:
    if not _DEFAULT_STATEMENT.exists():
        return "No statement found to analyze."
    txns = categorize(load_transactions(_DEFAULT_STATEMENT))
    if not txns:
        return "No transactions found."
    as_of = max(t.date for t in txns)
    sts = safe_to_spend(txns, as_of)
    return f"Safe to spend per day: ${sts.per_day:,.2f}"


def _scan_signals_tool(watchlist: str, windfall: float) -> str:
    tickers = [t.strip() for t in watchlist.split(",") if t.strip()]
    if not tickers:
        return "No watchlist provided."
    # Use empty headlines file since we are passing None anyway; signal_agent defaults to hitting news API if set
    signals = scan_signals(tickers, Decimal(str(windfall)))
    if not signals:
        return "No signals found."
    return "\n".join(f"[{s.conviction.upper()}] {s.ticker}: {s.play}" for s in signals)


TOOLS: Dict[str, Tool] = {
    "ask_mentor": Tool(
        name="ask_mentor",
        description="General questions about money, life, spending, values, or anything unspecified.",
        func=lambda question: Mentor().ask(question).answer,
        arg_hint='{"question": "string"}'
    ),
    "convene_board": Tool(
        name="convene_board",
        description="Major life decisions, big purchases, career moves, or asking for advice on a trade-off.",
        func=lambda decision: convene_board(decision).verdict,
        arg_hint='{"decision": "string"}'
    ),
    "finance_summary": Tool(
        name="finance_summary",
        description="Get a high-level summary of recent total income, total spend, and savings rate.",
        func=lambda: _finance_summary_tool(),
        arg_hint='{}'
    ),
    "safe_to_spend": Tool(
        name="safe_to_spend",
        description="Ask exactly how much money is safe to spend today/per day.",
        func=lambda: _safe_to_spend_tool(),
        arg_hint='{}'
    ),
    "scan_signals": Tool(
        name="scan_signals",
        description="Scan the market for trading signals on a watchlist.",
        func=lambda watchlist, windfall: _scan_signals_tool(watchlist, windfall),
        arg_hint='{"watchlist": "string, e.g. AAPL,MSFT", "windfall": float}'
    )
}


class Orchestrator:
    """Entry point router that selects and executes a tool."""

    def __init__(self):
        self.llm = ProviderFactory.get_llm()
        self.default_tool = "ask_mentor"

    def route(self, user_input: str) -> dict:
        """Determines which tool to use via LLM structured output."""
        tool_descriptions = "\n".join(
            f"- {t.name}: {t.description}\n  Args: {t.arg_hint}" 
            for t in TOOLS.values()
        )
        
        prompt = (
            f"You are the main router for a personal Life OS. Pick the BEST tool for the user's input.\n"
            f"Available tools:\n{tool_descriptions}\n\n"
            f"Output exactly one JSON object with 'tool' (string) and 'args' (object matching the arg_hint).\n"
            f"User input: {user_input}\n\n"
            f"Output JSON:"
        )
        
        try:
            raw_response = self.llm.generate(prompt, temperature=0.1, max_tokens=2048)
            match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if not match:
                raise ValueError("No JSON object found")
                
            parsed = json.loads(match.group(0))
            tool_name = parsed.get("tool")
            args = parsed.get("args", {})
            
            if tool_name not in TOOLS:
                return {"tool": self.default_tool, "args": {"question": user_input}}
                
            return {"tool": tool_name, "args": args}
        except Exception:
            # Safe fallback on parsing error
            return {"tool": self.default_tool, "args": {"question": user_input}}

    def run(self, user_input: str) -> OrchestratorResult:
        """Routes and executes the tool."""
        routing = self.route(user_input)
        tool_name = routing["tool"]
        args = routing["args"]
        
        tool = TOOLS.get(tool_name)
        if not tool:
            # Defensive check, shouldn't happen because of route() fallback
            tool_name = self.default_tool
            tool = TOOLS[tool_name]
            args = {"question": user_input}
            
        try:
            output = tool.func(**args)
            return OrchestratorResult(tool_used=tool_name, args=args, output=output)
        except Exception:
            # Fallback if the arguments provided by the LLM don't match the function signature
            # or if the function itself crashes.
            try:
                fallback_tool = TOOLS[self.default_tool]
                output = fallback_tool.func(question=user_input)
                return OrchestratorResult(tool_used=self.default_tool, args={"question": user_input}, output=output)
            except Exception as fallback_err:
                return OrchestratorResult(tool_used=self.default_tool, args={"question": user_input}, output=f"Error: {fallback_err}")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
        
    parser = argparse.ArgumentParser(description="Life OS Orchestrator.")
    parser.add_argument("input", help="What do you want to ask or do?")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  LIFE OS ORCHESTRATOR")
    print("=" * 60)
    
    orch = Orchestrator()
    result = orch.run(args.input)
    
    print(f"Tool selected : {result.tool_used}")
    print(f"Arguments     : {result.args}")
    print("-" * 60)
    print(result.output)
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
