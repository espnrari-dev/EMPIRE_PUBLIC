#!/usr/bin/env python3
"""Legendary Investor Strategy Scores for SHOGUN.
All scores are computed from real-time market/on-chain data + social sentiment.
Each score ranges 0 (bad) to 1 (excellent).
"""

def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))

def compute_buffett_score(obs, onchain, sentiment):
    """
    Warren Buffett: Value & Margin of Safety.
    Prefers liquid assets, stable prices, positive sentiment, and reasonable volume/mcap.
    """
    liquidity = obs.get("liquidity_usd", 0) or 0
    volume = obs.get("volume_24h_usd", 0) or 0
    change = obs.get("price_change_24h", 0) or 0
    mcap = onchain.get("coingecko_market_cap") or onchain.get("market_cap_from_supply") or 0

    liq_score = _clamp(liquidity / 1_000_000)          # >$1M liquidity = good
    vol_score = _clamp(volume / 100_000)               # >$100k volume = good
    stability = _clamp(1.0 - abs(change) / 50.0)       # stable price = good
    sentiment_score = _clamp(max(0.0, sentiment))      # positive sentiment = good

    if mcap > 0:
        # Volume relative to market cap: active trading suggests fair valuation
        value_score = _clamp(volume / mcap * 100)
    else:
        value_score = 0.0

    score = 0.30*liq_score + 0.20*vol_score + 0.20*stability + 0.20*sentiment_score + 0.10*value_score
    return _clamp(score)

def compute_munger_score(obs, onchain, sentiment):
    """
    Charlie Munger: Quality & Circle of Competence.
    Avoids extreme volatility, scams, and illiquid assets. Requires stability and good liquidity.
    """
    liquidity = obs.get("liquidity_usd", 0) or 0
    change = obs.get("price_change_24h", 0) or 0
    mcap = onchain.get("coingecko_market_cap") or onchain.get("market_cap_from_supply") or 0

    stability = _clamp(1.0 - abs(change) / 30.0)       # stricter stability requirement
    liq_score = _clamp(liquidity / 2_000_000)          # higher liquidity bar
    sentiment_score = _clamp(max(0.0, sentiment))

    # Penalize strongly negative sentiment (scam risk)
    penalty = 0.5 if sentiment < -0.2 else 1.0

    if mcap > 0:
        activity = _clamp((obs.get("volume_24h_usd", 0) or 0) / mcap * 10)
    else:
        activity = 0.0

    score = (0.40*stability + 0.30*liq_score + 0.20*sentiment_score + 0.10*activity) * penalty
    return _clamp(score)

def compute_fink_score(obs, onchain, sentiment):
    """
    Larry Fink: Risk Management & Long-Term Macro Stability.
    Rewards low volatility, healthy volume, reasonable gas prices, and mid-cap stability.
    """
    change = obs.get("price_change_24h", 0) or 0
    volume = obs.get("volume_24h_usd", 0) or 0
    gas = onchain.get("gas_price_gwei") or 0
    mcap = onchain.get("coingecko_market_cap") or onchain.get("market_cap_from_supply") or 0

    volatility = _clamp(1.0 - abs(change) / 40.0)      # moderate volatility tolerance
    vol_score = _clamp(volume / 100_000)               # healthy volume
    gas_score = _clamp(1.0 - min(gas, 100) / 100.0)    # lower gas = healthier network

    # Fink prefers established assets: mid-cap sweet spot
    if 10_000_000 <= mcap <= 1_000_000_000:
        mcap_score = 1.0
    elif mcap > 0:
        mcap_score = 0.5
    else:
        mcap_score = 0.0

    score = 0.30*volatility + 0.30*vol_score + 0.20*gas_score + 0.20*mcap_score
    return _clamp(score)
