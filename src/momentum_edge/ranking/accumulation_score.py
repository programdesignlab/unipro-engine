"""
M6 — Institutional Accumulation Detection (max 15 pts).

Signals:
  1. Rising delivery % over last 10 sessions (0-4 pts)
  2. Up-day volume > down-day volume ratio (0-4 pts)
  3. Volume contraction during consolidation (0-3 pts)
  4. Market cap > ₹800 crore (0-2 pts)
  5. Avg daily traded value > ₹5 crore (0-2 pts)
"""

from datetime import date, timedelta

import numpy as np
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


def score_accumulation(db: Session, stock_id: int, symbol: str, target_date: date) -> dict:
    """
    Compute accumulation score for a single stock.
    Returns dict with component scores and total (max 15).
    """
    # Get last 30 trading days of price + delivery data
    rows = db.execute(
        text("""
            SELECT e.date, e.open, e.close, e.volume,
                   d.delivery_pct, d.traded_qty
            FROM eod_prices e
            LEFT JOIN delivery_data d ON d.stock_id = e.stock_id AND d.date = e.date
            WHERE e.stock_id = :stock_id AND e.date <= :target_date
            ORDER BY e.date DESC
            LIMIT 30
        """),
        {"stock_id": stock_id, "target_date": target_date},
    ).fetchall()

    if len(rows) < 10:
        return {"symbol": symbol, "total": 0.0, "detail": "insufficient data"}

    # Reverse to chronological order
    rows = list(reversed(rows))

    dates = [r[0] for r in rows]
    opens = np.array([r[1] for r in rows])
    closes = np.array([r[2] for r in rows])
    volumes = np.array([r[3] for r in rows])
    delivery_pcts = [r[4] for r in rows]
    traded_qtys = [r[5] for r in rows]

    # 1. Rising delivery % over last 10 sessions (0-4 pts)
    recent_delivery = [d for d in delivery_pcts[-10:] if d is not None]
    if len(recent_delivery) >= 5:
        first_half = np.mean(recent_delivery[:len(recent_delivery)//2])
        second_half = np.mean(recent_delivery[len(recent_delivery)//2:])
        delivery_trend = second_half - first_half
        score_delivery = min(4.0, max(0.0, delivery_trend / 5.0 * 4.0))
    else:
        score_delivery = 0.0

    # 2. Up-day vs down-day volume ratio (0-4 pts)
    up_vol = []
    down_vol = []
    for i in range(len(closes)):
        if closes[i] > opens[i]:
            up_vol.append(volumes[i])
        elif closes[i] < opens[i]:
            down_vol.append(volumes[i])

    if up_vol and down_vol:
        ratio = np.mean(up_vol) / np.mean(down_vol)
        score_updown = min(4.0, max(0.0, (ratio - 1.0) * 4.0))
    else:
        score_updown = 2.0  # neutral

    # 3. Volume contraction during consolidation (0-3 pts)
    # Check if recent volume is decreasing while price range is tightening
    if len(volumes) >= 20:
        vol_first = np.mean(volumes[:10])
        vol_last = np.mean(volumes[-10:])
        price_range_first = (np.max(closes[:10]) - np.min(closes[:10])) / np.mean(closes[:10]) * 100
        price_range_last = (np.max(closes[-10:]) - np.min(closes[-10:])) / np.mean(closes[-10:]) * 100

        vol_contracting = vol_last < vol_first * 0.8
        price_tightening = price_range_last < price_range_first

        if vol_contracting and price_tightening:
            score_contraction = 3.0
        elif vol_contracting or price_tightening:
            score_contraction = 1.5
        else:
            score_contraction = 0.0
    else:
        score_contraction = 0.0

    # 4. Market cap > ₹800 crore (0-2 pts)
    mcap_row = db.execute(
        text("SELECT market_cap FROM stocks WHERE id = :stock_id"),
        {"stock_id": stock_id},
    ).fetchone()
    market_cap = mcap_row[0] if mcap_row and mcap_row[0] else 0

    if market_cap > 80000:  # yfinance gives market cap in crores * 10M sometimes; adjust
        score_mcap = 2.0
    elif market_cap > 40000:
        score_mcap = 1.0
    else:
        score_mcap = 0.0

    # 5. Avg daily traded value > ₹5 crore (0-2 pts)
    avg_traded = np.mean([t for t in traded_qtys if t is not None]) if any(t is not None for t in traded_qtys) else 0
    avg_price = np.mean(closes[-10:])
    avg_traded_value = avg_traded * avg_price / 1e7  # in crores

    if avg_traded_value > 50:
        score_liquidity = 2.0
    elif avg_traded_value > 5:
        score_liquidity = 1.0
    else:
        score_liquidity = 0.0

    total = round(score_delivery + score_updown + score_contraction + score_mcap + score_liquidity, 1)

    return {
        "symbol": symbol,
        "total": min(15.0, total),
        "score_delivery_trend": round(score_delivery, 1),
        "score_updown_volume": round(score_updown, 1),
        "score_vol_contraction": round(score_contraction, 1),
        "score_market_cap": round(score_mcap, 1),
        "score_liquidity": round(score_liquidity, 1),
    }
