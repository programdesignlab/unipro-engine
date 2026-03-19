"""
M4 — Multi-timeframe Momentum Score (max 40 pts).

Factors:
  1. 12-month momentum excl. last month (0-10 pts)
  2. 6-month momentum (0-10 pts)
  3. 3-month momentum (0-8 pts)
  4. Relative strength vs Nifty 50 (0-7 pts)
  5. Proximity to 52-week high (0-5 pts)

All calculations use parquet data for speed.
"""

from datetime import date

import numpy as np
from loguru import logger

from momentum_edge.data.parquet_store import read_prices, read_nifty_index


def score_momentum(symbol: str, target_date: date) -> dict:
    """
    Compute momentum score for a single stock.
    Returns dict with component scores and total (max 40).
    """
    prices = read_prices(symbols=[symbol])
    prices = prices[prices["date"] <= target_date].sort_values("date")

    if len(prices) < 252:
        return {"symbol": symbol, "total": 0.0, "detail": "insufficient data"}

    close = prices["close"].values
    high = prices["high"].values
    current = close[-1]

    # 1. 12-month momentum excl. last month (0-10 pts)
    # ~252 trading days = 12 months, ~21 = 1 month
    if len(close) >= 252:
        price_12m_ago = close[-252]
        price_1m_ago = close[-21]
        mom_12m_ex1m = (price_1m_ago / price_12m_ago - 1) * 100
    else:
        mom_12m_ex1m = 0.0

    # 2. 6-month momentum (0-10 pts)
    if len(close) >= 126:
        price_6m_ago = close[-126]
        mom_6m = (current / price_6m_ago - 1) * 100
    else:
        mom_6m = 0.0

    # 3. 3-month momentum (0-8 pts)
    if len(close) >= 63:
        price_3m_ago = close[-63]
        mom_3m = (current / price_3m_ago - 1) * 100
    else:
        mom_3m = 0.0

    # 4. Relative strength vs Nifty (0-7 pts)
    nifty = read_nifty_index()
    nifty = nifty[nifty["date"] <= target_date].sort_values("date")
    if len(nifty) >= 126:
        nifty_6m_return = (nifty["close"].iloc[-1] / nifty["close"].iloc[-126] - 1) * 100
        rs = mom_6m - nifty_6m_return
    else:
        rs = 0.0

    # 5. Proximity to 52-week high (0-5 pts)
    lookback = min(252, len(high))
    high_52w = high[-lookback:].max()
    proximity = (current / high_52w) * 100 if high_52w > 0 else 0

    # Score each factor
    # 12m ex 1m: 0-10 pts, scaled. >50% = 10, <0% = 0
    score_12m = min(10.0, max(0.0, mom_12m_ex1m / 5.0))

    # 6m: 0-10 pts. >40% = 10, <0% = 0
    score_6m = min(10.0, max(0.0, mom_6m / 4.0))

    # 3m: 0-8 pts. >30% = 8, <0% = 0
    score_3m = min(8.0, max(0.0, mom_3m * 8.0 / 30.0))

    # RS: 0-7 pts. >20% outperformance = 7, <0% = 0
    score_rs = min(7.0, max(0.0, rs * 7.0 / 20.0))

    # Proximity: 0-5 pts. At high = 5, 25% below = 0
    score_prox = min(5.0, max(0.0, (proximity - 75) / 5.0))

    total = round(score_12m + score_6m + score_3m + score_rs + score_prox, 1)

    return {
        "symbol": symbol,
        "total": min(40.0, total),
        "mom_12m_ex1m": round(mom_12m_ex1m, 2),
        "mom_6m": round(mom_6m, 2),
        "mom_3m": round(mom_3m, 2),
        "rs_vs_nifty": round(rs, 2),
        "proximity_52w_high": round(proximity, 1),
        "score_12m": round(score_12m, 1),
        "score_6m": round(score_6m, 1),
        "score_3m": round(score_3m, 1),
        "score_rs": round(score_rs, 1),
        "score_prox": round(score_prox, 1),
    }


def score_all_momentum(symbols: list[str], target_date: date) -> dict[str, dict]:
    """Score momentum for all symbols. Returns {symbol: score_dict}."""
    results = {}
    for sym in symbols:
        results[sym] = score_momentum(sym, target_date)
    logger.info(f"[M4] Momentum scored for {len(results)} stocks")
    return results
