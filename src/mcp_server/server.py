"""Life OS MCP Server.

Exposes the core agent capabilities as MCP tools.
Run with: python -m src.mcp_server.server
"""

import sys
from decimal import Decimal
from pathlib import Path
from fastmcp import FastMCP

# Import agent functions
from src.agents.mentor import Mentor
from src.agents.board import convene_board as _board_convene
from src.agents.signal_agent import scan as _scan_sigs
from src.finance.analyze import analyze
from src.finance.categorize import categorize
from src.finance.safe_to_spend import safe_to_spend
from src.finance.statements import load_transactions

# Initialize FastMCP server
mcp = FastMCP("life-os")


@mcp.tool()
def get_finance_summary(statement_path: str) -> dict:
    """Analyze a financial statement and return a summary of spending by category.
    
    Args:
        statement_path: Absolute or relative path to the CSV statement.
    """
    try:
        path = Path(statement_path)
        if not path.exists():
            return {"status": "error", "error": f"File not found: {statement_path}"}
            
        txns = categorize(load_transactions(path))
        summary = analyze(txns)
        return {
            "status": "success",
            "total_income": float(summary.total_income),
            "total_spend": float(summary.total_spend),
            "net": float(summary.net),
            "savings_rate": summary.savings_rate
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def safe_to_spend_today(statement_path: str) -> dict:
    """Calculate the safe amount to spend per day for the rest of the month.
    
    Args:
        statement_path: Absolute or relative path to the CSV statement.
    """
    try:
        path = Path(statement_path)
        if not path.exists():
            return {"status": "error", "error": f"File not found: {statement_path}"}
            
        txns = categorize(load_transactions(path))
        as_of = max(t.date for t in txns)
        sts = safe_to_spend(txns, as_of)
        
        return {
            "status": "success",
            "safe_to_spend_usd": float(sts.per_day)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def convene_board(decision: str) -> dict:
    """Convene the Board of Directors to rule on a financial decision."""
    try:
        ruling = _board_convene(decision)
        return {
            "status": "success",
            "verdict": ruling.verdict,
            # Convert Opinion dataclasses to dicts so MCP can JSON-serialize them.
            "opinions": [{"persona": o.persona, "text": o.text} for o in ruling.opinions],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def ask_mentor(question: str) -> str:
    """Ask the grounded financial Mentor a question."""
    try:
        response = Mentor().ask(question)
        if response.sources:
            return f"{response.answer}\n\nSources:\n" + "\n".join(response.sources)
        return response.answer
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def scan_signals(watchlist: str, windfall_usd: float) -> list:
    """Scan the market for trading signals within a specified windfall cap.
    
    Args:
        watchlist: Comma-separated list of stock tickers (e.g. 'AAPL,MSFT')
        windfall_usd: The maximum amount to invest
    """
    try:
        tickers = [t.strip() for t in watchlist.split(",") if t.strip()]
        signals = _scan_sigs(tickers, Decimal(str(windfall_usd)))
        
        # We return a list of dicts instead of objects for MCP serialization
        return [
            {
                "ticker": s.ticker,
                "play": s.play,
                "conviction": s.conviction,
                "suggested_size_usd": float(s.suggested_size_usd)
            }
            for s in signals
        ]
    except Exception as e:
        return [{"status": "error", "error": str(e)}]


if __name__ == "__main__":
    # Force UTF-8 encoding for Windows stdio
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    
    mcp.run()
