"""
M8 — Breakout Pattern Detection.

Detects patterns for stocks that have passed the Trend Template:
  1. Volatility Contraction Pattern (VCP) — progressively tighter swings
  2. Tight consolidation base — price range <10% over 5+ weeks
  3. Resistance breakout — price breaks above prior pivot high on volume
  4. Volume expansion breakout — volume surge >2x 50-day average on up-day

Returns pattern type, signal strength, and breakout score (max 10 pts).
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class PatternResult:
    symbol: str
    pattern_type: str | None  # VCP, Base, Resistance, VolumeBreakout, or None
    signal_strength: str      # Very High, High, Medium, Low, None
    breakout_score: float     # max 10 pts
    stop_loss_level: float | None  # suggested stop-loss price


def detect_pattern(db: Session, stock_id: int, symbol: str, target_date: date) -> PatternResult:
    """
    Detect breakout patterns for a single stock.
    Requires at least 60 days of price data.
    """
    rows = db.execute(
        text("""
            SELECT date, open, high, low, close, volume
            FROM eod_prices
            WHERE stock_id = :stock_id AND date <= :target_date
            ORDER BY date DESC
            LIMIT 60
        """),
        {"stock_id": stock_id, "target_date": target_date},
    ).fetchall()

    if len(rows) < 30:
        return PatternResult(symbol=symbol, pattern_type=None,
                             signal_strength="None", breakout_score=0.0, stop_loss_level=None)

    # Reverse to chronological
    rows = list(reversed(rows))

    highs = np.array([r[2] for r in rows], dtype=float)
    lows = np.array([r[3] for r in rows], dtype=float)
    closes = np.array([r[4] for r in rows], dtype=float)
    volumes = np.array([r[5] for r in rows], dtype=float)

    current_close = closes[-1]
    current_volume = volumes[-1]
    avg_volume_50 = np.mean(volumes[-50:]) if len(volumes) >= 50 else np.mean(volumes)

    best_pattern = None
    best_score = 0.0
    best_strength = "None"
    stop_loss = None

    # 1. VCP Detection: progressively tighter price swings over 3+ weeks
    n = len(closes)
    if n >= 30:
        # Split last 30 days into 3 periods of 10
        ranges = []
        for i in range(3):
            s = n - 30 + i * 10
            e = s + 10
            period_range = (np.max(highs[s:e]) - np.min(lows[s:e])) / np.mean(closes[s:e]) * 100
            ranges.append(period_range)

        # VCP: each period's range should be smaller than the previous
        if ranges[0] > ranges[1] > ranges[2] and ranges[2] < 8:
            contraction_ratio = ranges[2] / ranges[0] if ranges[0] > 0 else 1
            if contraction_ratio < 0.5:
                best_pattern = "VCP"
                best_score = 10.0
                best_strength = "Very High"
            else:
                best_pattern = "VCP"
                best_score = 7.0
                best_strength = "High"
            stop_loss = float(np.min(lows[-10:]))

    # 2. Tight consolidation base: price range <10% over last 25+ days
    if len(closes) >= 25:
        base_range = (np.max(highs[-25:]) - np.min(lows[-25:])) / np.mean(closes[-25:]) * 100
        vol_declining = np.mean(volumes[-10:]) < np.mean(volumes[-25:-10]) * 0.85

        if base_range < 10 and vol_declining and (best_score < 8.0):
            best_pattern = "Base"
            best_score = 8.0
            best_strength = "High"
            stop_loss = float(np.min(lows[-25:]))

    # 3. Resistance breakout: price breaks above prior pivot high on volume
    if len(closes) >= 20:
        # Find pivot high in days -20 to -5
        pivot_range_highs = highs[-20:-5]
        pivot_high = np.max(pivot_range_highs)
        volume_surge = current_volume > avg_volume_50 * 1.5

        if current_close > pivot_high and volume_surge and (best_score < 8.0):
            best_pattern = "Resistance"
            best_score = 8.0
            best_strength = "High"
            stop_loss = float(pivot_high * 0.97)  # 3% below breakout level

    # 4. Volume expansion breakout: volume >2x average on up-day near highs
    if len(closes) >= 2:
        is_up_day = current_close > closes[-2]
        near_high = current_close >= np.max(highs[-20:]) * 0.98 if len(highs) >= 20 else False
        vol_2x = current_volume > avg_volume_50 * 2.0

        if is_up_day and near_high and vol_2x and (best_score < 6.0):
            best_pattern = "VolumeBreakout"
            best_score = 6.0
            best_strength = "Medium"
            stop_loss = float(lows[-1])  # day's low

    if best_pattern is None:
        best_score = 0.0
        best_strength = "None"

    return PatternResult(
        symbol=symbol,
        pattern_type=best_pattern,
        signal_strength=best_strength,
        breakout_score=round(best_score, 1),
        stop_loss_level=round(stop_loss, 2) if stop_loss else None,
    )
