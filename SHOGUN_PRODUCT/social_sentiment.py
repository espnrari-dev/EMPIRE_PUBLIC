#!/usr/bin/env python3
"""Real-time social sentiment from Reddit (no auth, real data)."""
import requests, time
from typing import Optional

POSITIVE_WORDS = {"moon", "bullish", "buy", "gem", "rocket", "pump", "gain", "profit", "ath", "long"}
NEGATIVE_WORDS = {"dump", "bearish", "sell", "scam", "rug", "fud", "short", "dip", "crash", "dead"}

def get_reddit_mentions(symbol: str, limit: int = 10) -> list:
    """Fetch recent Reddit posts mentioning the symbol."""
    query = f'"{symbol}" OR "{symbol} coin"'
    url = "https://www.reddit.com/search.json"
    params = {"q": query, "limit": limit, "sort": "new", "t": "day"}
    try:
        resp = requests.get(url, params=params, headers={"User-Agent": "SHOGUN/1.0"}, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("children", [])
    except Exception:
        pass
    return []

def analyze_sentiment(posts: list) -> float:
    """Compute sentiment score from -1 (very negative) to +1 (very positive)."""
    if not posts:
        return 0.0
    score = 0.0
    for post in posts:
        data = post.get("data", {})
        text = (data.get("title", "") + " " + data.get("selftext", "")).lower()
        pos = sum(1 for w in POSITIVE_WORDS if w in text)
        neg = sum(1 for w in NEGATIVE_WORDS if w in text)
        score += (pos - neg) / max(len(text.split()), 1)  # normalized by word count
    return max(-1.0, min(1.0, score / len(posts)))

def get_social_sentiment(symbol: str) -> float:
    posts = get_reddit_mentions(symbol)
    return analyze_sentiment(posts)

if __name__ == "__main__":
    s = get_social_sentiment("Mog Coin")
    print(f"Sentiment for 'Mog Coin': {s}")
