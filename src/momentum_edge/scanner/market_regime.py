"""
M2 — Market Regime Detection.

Classifies the broad market as Bull, Neutral, or Bear based on:
  1. Nifty 50 vs its 200-day MA
  2. % of stocks trading above their 50-day MA
  3. New 52-week highs vs new 52-week lows

Returns regime classification and recommended exposure level.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


class Regime(str, Enum):
    BULL = "Bull"
    NEUTRAL = "Neutral"
    BEAR = "Bear"


@dataclass
class RegimeResult:
    regime: Regime
    nifty_above_200ma: bool
    pct_above_50ma: float  # 0-100
    highs_gt_lows: bool
    signals_positive: int  # out of 3
    exposure: str  # Aggressive / Moderate / Defensive


def classify_regime(db: Session, target_date: date) -> RegimeResult:
    """
    Classify market regime for a given date.
    Requires indicators table to be populated for target_date.
    """
    from momentum_edge.data.parquet_store import read_nifty_index

    # 1. Nifty 50 vs 200-day MA
    nifty = read_nifty_index()
    nifty = nifty[nifty["date"] <= target_date].sort_values("date")

    if len(nifty) < 200:
        logger.warning("[M2] Not enough Nifty history for regime detection")
        return RegimeResult(
            regime=Regime.NEUTRAL,
            nifty_above_200ma=False,
            pct_above_50ma=50.0,
            highs_gt_lows=False,
            signals_positive=0,
            exposure="Moderate",
        )

    nifty_close = nifty["close"].iloc[-1]
    nifty_ma200 = nifty["close"].tail(200).mean()
    nifty_above_200ma = nifty_close > nifty_ma200

    # 2. % of stocks above their 50-day MA (from indicators table)
    row = db.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE i.ma50 IS NOT NULL AND e.close > i.ma50) AS above_50ma
            FROM indicators i
            JOIN stocks s ON s.id = i.stock_id
            JOIN eod_prices e ON e.stock_id = i.stock_id AND e.date = i.date
            WHERE i.date = :target_date AND s.is_active = true
        """),
        {"target_date": target_date},
    ).fetchone()

    total = row[0] if row else 0
    above_50ma = row[1] if row else 0
    pct_above_50ma = (above_50ma / total * 100) if total > 0 else 50.0

    # 3. New 52-week highs vs lows
    hl_row = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE e.close >= i.high_52w * 0.97) AS near_highs,
                COUNT(*) FILTER (WHERE e.close <= i.low_52w * 1.03) AS near_lows
            FROM indicators i
            JOIN eod_prices e ON e.stock_id = i.stock_id AND e.date = i.date
            JOIN stocks s ON s.id = i.stock_id
            WHERE i.date = :target_date AND s.is_active = true
        """),
        {"target_date": target_date},
    ).fetchone()

    near_highs = hl_row[0] if hl_row else 0
    near_lows = hl_row[1] if hl_row else 0
    highs_gt_lows = near_highs > near_lows

    # Classification
    signals_positive = sum([nifty_above_200ma, pct_above_50ma > 60, highs_gt_lows])

    if signals_positive >= 3:
        regime = Regime.BULL
        exposure = "Aggressive"
    elif signals_positive >= 2:
        regime = Regime.NEUTRAL
        exposure = "Moderate"
    else:
        regime = Regime.BEAR
        exposure = "Defensive"

    result = RegimeResult(
        regime=regime,
        nifty_above_200ma=nifty_above_200ma,
        pct_above_50ma=round(pct_above_50ma, 1),
        highs_gt_lows=highs_gt_lows,
        signals_positive=signals_positive,
        exposure=exposure,
    )

    logger.info(
        f"[M2] Regime: {regime.value} | Nifty>200MA: {nifty_above_200ma} | "
        f">50MA: {pct_above_50ma:.0f}% | H>L: {highs_gt_lows} | Exposure: {exposure}"
    )

    return result
