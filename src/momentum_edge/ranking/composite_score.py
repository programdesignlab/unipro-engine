"""
M9 — Composite Score (uncapped).

v7 aggregation — no hard max since scaled_score is percentile-based (0-100)
plus vol scaling:
  - scaled_score:       from indicators (percentile momentum + vol scaling)
  - fundamental_bonus:  from fundamental_bonus.py (-5 to +20)
  - accumulation_score: from accumulation_score.py (0-11)
  - sector_bonus:       from sector_rotation.py (-5, 0, or +10)
  - technical_score:    from trend_template.py (0-15)
  - breakout_score:     from breakout_patterns.py (0-10)

Writes to the scores table.
"""

from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


def compute_composite(
    db: Session,
    stock_id: int,
    target_date: date,
    scaled_score: float,
    fundamental_bonus: float,
    accumulation_score: float,
    sector_bonus: float,
    technical_score: float,
    breakout_score: float,
) -> float:
    """
    Compute and store composite score for a stock.
    Returns composite score (no cap).
    """
    # Ensure all scores are native Python floats (not numpy)
    scaled_score = float(scaled_score)
    fundamental_bonus = float(fundamental_bonus)
    accumulation_score = float(accumulation_score)
    sector_bonus = float(sector_bonus)
    technical_score = float(technical_score)
    breakout_score = float(breakout_score)

    composite = round(
        scaled_score + fundamental_bonus + accumulation_score +
        sector_bonus + technical_score + breakout_score,
        1,
    )

    # Upsert into scores table (map v7 names to existing columns)
    # momentum_score ← scaled_score, fundamental_score ← fundamental_bonus, sector_score ← sector_bonus
    db.execute(
        text("""
            INSERT INTO scores (stock_id, date, momentum_score, fundamental_score,
                                sector_score, technical_score, accumulation_score,
                                breakout_score, composite_score)
            VALUES (:stock_id, :date, :momentum, :fundamental, :sector,
                    :technical, :accumulation, :breakout, :composite)
            ON CONFLICT (stock_id, date) DO UPDATE SET
                momentum_score    = EXCLUDED.momentum_score,
                fundamental_score = EXCLUDED.fundamental_score,
                sector_score      = EXCLUDED.sector_score,
                technical_score   = EXCLUDED.technical_score,
                accumulation_score = EXCLUDED.accumulation_score,
                breakout_score    = EXCLUDED.breakout_score,
                composite_score   = EXCLUDED.composite_score
        """),
        {
            "stock_id": stock_id,
            "date": target_date,
            "momentum": scaled_score,
            "fundamental": fundamental_bonus,
            "sector": sector_bonus,
            "technical": technical_score,
            "accumulation": accumulation_score,
            "breakout": breakout_score,
            "composite": composite,
        },
    )

    return composite
