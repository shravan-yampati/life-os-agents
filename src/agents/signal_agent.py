"""Signal Agent — opportunistic options plays bounded by the windfall bucket."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass, asdict
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

from src.config import settings
from src.providers.factory import ProviderFactory
from src.signals.sources import fetch_news, fetch_trends

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FOUNDATION_PATH = _REPO_ROOT / "brainstorms" / "life-os-foundation.md"
_LEDGER_PATH = _REPO_ROOT / ".raglab" / "signals_log.jsonl"


@dataclass
class Signal:
    signal_id: str
    ticker: str
    catalyst: str
    play: str
    conviction: str
    suggested_size_usd: Decimal
    rationale: str
    status: str = "open"
    outcome: Optional[str] = None
    pnl: Optional[Decimal] = None


def log_signals(signals: List[Signal], ledger_path: Path = _LEDGER_PATH) -> None:
    """Appends new signals to the JSONL ledger."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        for s in signals:
            d = asdict(s)
            d["suggested_size_usd"] = float(d["suggested_size_usd"])
            if d["pnl"] is not None:
                d["pnl"] = float(d["pnl"])
            f.write(json.dumps(d) + "\n")


def record_outcome(signal_id: str, outcome: str, pnl: Decimal, ledger_path: Path = _LEDGER_PATH) -> bool:
    """Updates the outcome of an existing signal in the ledger."""
    if not ledger_path.exists():
        return False
        
    updated = False
    lines = ledger_path.read_text(encoding="utf-8").strip().split("\n")
    with ledger_path.open("w", encoding="utf-8") as f:
        for line in lines:
            if not line:
                continue
            d = json.loads(line)
            if d["signal_id"] == signal_id:
                d["outcome"] = outcome
                d["pnl"] = float(pnl)
                d["status"] = "closed"
                updated = True
            f.write(json.dumps(d) + "\n")
    return updated


def scan(
    watchlist: List[str], 
    windfall_usd: Decimal = Decimal("300"), 
    headlines_file: Optional[Path] = None,
    foundation_path: Path = _FOUNDATION_PATH
) -> List[Signal]:
    """Scans public catalysts and returns LLM-scored signals capped to windfall limit."""
    
    # 1. Gather Catalysts
    news_data = {}
    trends_data = fetch_trends(watchlist)
    
    for ticker in watchlist:
        # Pass headlines_file so offline testing is possible
        news_data[ticker] = fetch_news(query=ticker, api_key=settings.NEWS_API_KEY, headlines_file=headlines_file)
        
    # 2. Prepare Context
    if foundation_path.exists():
        foundation = foundation_path.read_text(encoding="utf-8")
    else:
        foundation = "(No foundation document found.)"

    data_context = json.dumps({
        "watchlist": watchlist,
        "windfall_limit": float(windfall_usd),
        "news": news_data,
        "trends": trends_data
    }, indent=2)
    
    # 3. LLM Prompt
    llm = ProviderFactory.get_llm()
    prompt = (
        f"You are the Life OS Signal Agent. Your job is to watch PUBLIC catalysts and suggest opportunistic plays.\n"
        f"HARD RULE: You can NEVER exceed the windfall limit of ${windfall_usd}.\n"
        f"HARD RULE: Return ONLY a valid JSON array of objects with keys: ticker, catalyst, play, conviction, suggested_size_usd, rationale.\n\n"
        f"--- WHO I AM & MY RULES ---\n{foundation}\n\n"
        f"--- DATA CONTEXT ---\n{data_context}\n\n"
        f"Output JSON:"
    )
    
    try:
        raw_response = llm.generate(prompt, temperature=0.2, max_tokens=2048)
        
        # Attempt to parse JSON response. Could contain markdown code blocks.
        clean_json = raw_response.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:-3].strip()
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:-3].strip()
            
        parsed = json.loads(clean_json)
        
        signals = []
        for p in parsed:
            size = Decimal(str(p.get("suggested_size_usd", "0")))
            # Enforce Windfall Cap
            capped_size = min(size, windfall_usd)
            
            sig = Signal(
                signal_id=str(uuid.uuid4())[:8],
                ticker=p.get("ticker", "UNKNOWN"),
                catalyst=p.get("catalyst", ""),
                play=p.get("play", ""),
                conviction=p.get("conviction", "low"),
                suggested_size_usd=capped_size,
                rationale=p.get("rationale", "")
            )
            signals.append(sig)
            
        return signals
    except Exception as e:
        print(f"Error generating signals: {e}")
        return []


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
        
    parser = argparse.ArgumentParser(description="Signal Agent for windfall opportunities.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # scan command
    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("--watchlist", required=True, help="Comma separated tickers (e.g. MU,NVDA)")
    scan_parser.add_argument("--windfall", default="300", help="Max allowed size in USD")
    scan_parser.add_argument("--headlines", help="Local JSON file with mock headlines for testing")
    
    # record command
    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--id", required=True, help="Signal ID")
    record_parser.add_argument("--outcome", required=True, choices=["win", "loss", "scratch"])
    record_parser.add_argument("--pnl", required=True, help="Profit/Loss amount")
    
    args = parser.parse_args()
    
    if args.command == "scan":
        tickers = [t.strip() for t in args.watchlist.split(",")]
        windfall = Decimal(args.windfall)
        headlines_path = Path(args.headlines) if args.headlines else None
        
        print("\n" + "=" * 60)
        print("  SIGNAL AGENT SCAN")
        print("=" * 60)
        
        signals = scan(tickers, windfall, headlines_path)
        if not signals:
            print("No signals generated.")
        else:
            for s in signals:
                print(f"\n[{s.conviction.upper()}] {s.ticker}: {s.play}")
                print(f"Catalyst: {s.catalyst}")
                print(f"Size: ${s.suggested_size_usd:.2f} (Cap: ${windfall:.2f})")
                print(f"Rationale: {s.rationale}")
                print(f"ID: {s.signal_id}")
            
            print("\n" + "-" * 60)
            print("DISCLAIMER: Informational, not financial advice — you place the trade yourself.")
            log_signals(signals)
            print(f"Logged {len(signals)} signals to ledger.")
            
    elif args.command == "record":
        pnl = Decimal(args.pnl)
        success = record_outcome(args.id, args.outcome, pnl)
        if success:
            print(f"Successfully recorded {args.outcome} with PNL ${pnl:.2f} for Signal {args.id}.")
        else:
            print(f"Failed to record outcome. Signal {args.id} not found in ledger.")

if __name__ == "__main__":
    main()
