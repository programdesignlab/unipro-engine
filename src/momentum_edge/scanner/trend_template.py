"""
M7 — Minervini Trend Template Screening.

All 6 conditions must be true for a stock to pass (hard filter):
  1. Current price > 50-day MA
  2. Current price > 150-day MA
  3. Current price > 200-day MA
  4. 50-day MA > 150-day MA
  5. 150-day MA > 200-day MA
  6. Current price within 25% of 52-week high

Returns pass/fail + a technical structure score (max 15 pts).
"""

from dataclasses import dataclass
from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class TrendTemplateResult:
    symbol: str
    passes: bool
    conditions_met: int  # out of 6
    technical_score: float  # max 15 pts
    details: dict  # individual condition results


def passes_trend_template(db: Session, stock_id: int, symbol: str, target_date: date) -> TrendTemplateResult:
    """
    Apply Minervini's 6-condition trend template.
    Returns TrendTemplateResult with pass/fail, conditions met, and technical score.
    """
    # Get indicators and current price
    row = db.execute(
        text("""
            SELECT e.close, i.ma50, i.ma150, i.ma200, i.high_52w, i.low_52w
            FROM indicators i
            JOIN eod_prices e ON e.stock_id = i.stock_id AND e.date = i.date
            WHERE i.stock_id = :stock_id AND i.date = :target_date
        """),
        {"stock_id": stock_id, "target_date": target_date},
    ).fetchone()

    if not row:
        return TrendTemplateResult(
            symbol=symbol, passes=False, conditions_met=0,
            technical_score=0.0, details={"error": "no indicator data"},
        )

    close, ma50, ma150, ma200, high_52w, low_52w = row

    if any(v is None for v in [close, ma50, ma150, ma200, high_52w]):
        return TrendTemplateResult(
            symbol=symbol, passes=False, conditions_met=0,
            technical_score=0.0, details={"error": "incomplete indicators"},
        )

    # 6 conditions
    c1 = close > ma50       # Price > 50MA
    c2 = close > ma150      # Price > 150MA
    c3 = close > ma200      # Price > 200MA
    c4 = ma50 > ma150       # 50MA > 150MA
    c5 = ma150 > ma200      # 150MA > 200MA
    c6 = close >= high_52w * 0.75  # Within 25% of 52w high

    conditions = [c1, c2, c3, c4, c5, c6]
    conditions_met = sum(conditions)
    passes = all(conditions)

    details = {
        "price_gt_ma50": c1,
        "price_gt_ma150": c2,
        "price_gt_ma200": c3,
        "ma50_gt_ma150": c4,
        "ma150_gt_ma200": c5,
        "within_25pct_52w_high": c6,
        "close": round(close, 2),
        "ma50": round(ma50, 2),
        "ma150": round(ma150, 2),
        "ma200": round(ma200, 2),
        "high_52w": round(high_52w, 2),
    }

    # Technical score (max 15): proportional to conditions met + bonus for proximity to high
    base_score = conditions_met / 6.0 * 12.0  # max 12 from conditions
    if high_52w > 0:
        proximity = close / high_52w
        proximity_bonus = min(3.0, max(0.0, (proximity - 0.75) / 0.25 * 3.0))
    else:
        proximity_bonus = 0.0

    technical_score = min(15.0, round(base_score + proximity_bonus, 1))

    return TrendTemplateResult(
        symbol=symbol,
        passes=passes,
        conditions_met=conditions_met,
        technical_score=technical_score,
        details=details,
    )
