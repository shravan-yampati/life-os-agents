"""Public signal sources for the Signal Agent."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx

try:
    from pytrends.request import TrendReq
    HAS_PYTRENDS = True
except ImportError:
    HAS_PYTRENDS = False


def fetch_news(query: str, api_key: Optional[str] = None, headlines_file: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    """Fetches public news headlines.
    
    If headlines_file is provided, reads a mock JSON array from that file instead.
    """
    if headlines_file and Path(headlines_file).exists():
        try:
            return json.loads(Path(headlines_file).read_text(encoding="utf-8"))
        except Exception:
            return []
            
    if not api_key:
        return []

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 5,
        "apiKey": api_key
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("articles", [])
    except Exception:
        return []


def fetch_trends(keywords: List[str]) -> Dict[str, Any]:
    """Fetches Google Trends interest over time using pytrends."""
    if not HAS_PYTRENDS or not keywords:
        return {}
        
    try:
        pytrends = TrendReq(hl='en-US', tz=360)
        kw_list = keywords[:5]
        pytrends.build_payload(kw_list, cat=0, timeframe='now 7-d', geo='', gprop='')
        df = pytrends.interest_over_time()
        
        if df.empty:
            return {}
            
        if 'isPartial' in df.columns:
            df = df.drop(columns=['isPartial'])
            
        # Convert Timestamp keys to strings for JSON serializability
        raw_dict = df.to_dict(orient="index")
        return {str(k): v for k, v in raw_dict.items()}
    except Exception:
        return {}
