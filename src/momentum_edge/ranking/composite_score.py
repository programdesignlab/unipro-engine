"""
M9 — Composite Score (max 125 pts).

Aggregates all module scores:
  - Momentum score (M4): max 40 pts
  - Fundamental score (M5): max 25 pts
  - Sector score (M3): max 20 pts
  - Technical score (M7): max 15 pts
  - Accumulation score (M6): max 15 pts
  - Breakout score (M8): max 10 pts
  Total: max 125 pts

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
    momentum_score: float,
    fundamental_score: float,
    sector_score: float,
    technical_score: float,
    accumulation_score: float,
    breakout_score: float,
) -> float:
    """
    Compute and store composite score for a stock.
    Returns composite score (max 125).
    """
    # Ensure all scores are native Python floats (not numpy)
    momentum_score = float(momentum_score)
    fundamental_score = float(fundamental_score)
    sector_score = float(sector_score)
    technical_score = float(technical_score)
    accumulation_score = float(accumulation_score)
    breakout_score = float(breakout_score)

    composite = round(
        momentum_score + fundamental_score + sector_score +
        technical_score + accumulation_score + breakout_score,
        1,
    )
    composite = min(125.0, composite)

    # Upsert into scores table
    db.execute(
        text("""
            INSERT INTO scores (stock_id, date, momentum_score, fundamental_score,
                                sector_score, technical_score, accumulation_score,
                                breakout_score, composite_score)
            VALUES (:stock_id, :date, :momentum, :fundamental, :sector,
                    :technical, :accumulation, :breakout, :composite)
            ON CONFLICT (stock_id, date) DO UPDATE SET
                momentum_score = EXCLUDED.momentum_score,
                fundamental_score = EXCLUDED.fundamental_score,
                sector_score = EXCLUDED.sector_score,
                technical_score = EXCLUDED.technical_score,
                accumulation_score = EXCLUDED.accumulation_score,
                breakout_score = EXCLUDED.breakout_score,
                composite_score = EXCLUDED.composite_score
        """),
        {
            "stock_id": stock_id,
            "date": target_date,
            "momentum": momentum_score,
            "fundamental": fundamental_score,
            "sector": sector_score,
            "technical": technical_score,
            "accumulation": accumulation_score,
            "breakout": breakout_score,
            "composite": composite,
        },
    )

    return composite
