"""
M7 — Minervini Trend Template Screening (v7).

All 8 conditions must be true for a stock to pass (hard filter):
  1. adj_close > 50-day MA
  2. adj_close > 150-day MA
  3. adj_close > 200-day MA
  4. 50-day MA > 150-day MA
  5. 150-day MA > 200-day MA
  6. 200-day MA slope rising (ma200_slope > 0)
  7. adj_close within 20% of 52-week high
  8. 20+ consecutive days above 200-day MA (stage 2 established)

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
    conditions_met: int  # 0-8
    technical_score: float  # max 15 pts
    details: dict  # individual condition results


def _check_stage2_established(
    db: Session, stock_id: int, target_date: date
) -> bool:
    """
    Check if adj_close > ma200 for the last 20 consecutive trading days
    up to and including target_date.
    """
    rows = db.execute(
        text("""
            SELECT e.adj_close, i.ma200
            FROM eod_prices e
            JOIN indicators i ON i.stock_id = e.stock_id AND i.date = e.date
            WHERE e.stock_id = :stock_id AND e.date <= :target_date
            ORDER BY e.date DESC
            LIMIT 20
        """),
        {"stock_id": stock_id, "target_date": target_date},
    ).fetchall()

    if len(rows) < 20:
        return False

    return all(
        adj_close is not None and ma200 is not None and adj_close > ma200
        for adj_close, ma200 in rows
    )


def passes_trend_template(
    db: Session, stock_id: int, symbol: str, target_date: date
) -> TrendTemplateResult:
    """
    Apply Minervini's 8-condition trend template (v7).
    Returns TrendTemplateResult with pass/fail, conditions met, and technical score.
    """
    # Get indicators and current adj_close price
    row = db.execute(
        text("""
            SELECT e.adj_close, i.ma50, i.ma150, i.ma200, i.ma200_slope, i.high_52w
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

    adj_close, ma50, ma150, ma200, ma200_slope, high_52w = row

    if any(v is None for v in [adj_close, ma50, ma150, ma200, ma200_slope, high_52w]):
        return TrendTemplateResult(
            symbol=symbol, passes=False, conditions_met=0,
            technical_score=0.0, details={"error": "incomplete indicators"},
        )

    # 8 conditions
    c1 = adj_close > ma50          # adj_close > 50MA
    c2 = adj_close > ma150         # adj_close > 150MA
    c3 = adj_close > ma200         # adj_close > 200MA
    c4 = ma50 > ma150              # 50MA > 150MA
    c5 = ma150 > ma200             # 150MA > 200MA
    c6 = ma200_slope > 0           # 200MA slope rising
    c7 = adj_close >= high_52w * 0.80  # Within 20% of 52w high
    c8 = _check_stage2_established(db, stock_id, target_date)  # 20 days above MA200

    conditions = [c1, c2, c3, c4, c5, c6, c7, c8]
    conditions_met = sum(conditions)
    passes = all(conditions)

    details = {
        "price_gt_ma50": c1,
        "price_gt_ma150": c2,
        "price_gt_ma200": c3,
        "ma50_gt_ma150": c4,
        "ma150_gt_ma200": c5,
        "ma200_slope_rising": c6,
        "within_20pct_52w_high": c7,
        "stage2_established_20d": c8,
        "adj_close": round(float(adj_close), 2),
        "ma50": round(float(ma50), 2),
        "ma150": round(float(ma150), 2),
        "ma200": round(float(ma200), 2),
        "ma200_slope": round(float(ma200_slope), 4),
        "high_52w": round(float(high_52w), 2),
    }

    # Technical score (max 15):
    #   Base: (conditions_met / 8) * 12  — max 12 from conditions
    #   Proximity bonus: up to 3 pts based on closeness to 52w high
    base_score = (conditions_met / 8.0) * 12.0
    if high_52w > 0:
        proximity = adj_close / high_52w
        proximity_bonus = min(3.0, max(0.0, (proximity - 0.80) / 0.20 * 3.0))
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
