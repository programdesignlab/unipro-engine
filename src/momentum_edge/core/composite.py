"""
Weighted composite scoring — reads weights from strategy YAML.

Replaces the naive sum in ranking/composite_score.py with configurable
weighted composition. Each scoring module's output is normalized by its
max_possible, then weighted per the strategy config.
"""

from __future__ import annotations

from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.core.strategy import ScoringConfig


def compute_composite(
    db: Session,
    stock_id: int,
    target_date: date,
    *,
    scaled_score: float,
    fundamental_bonus: float,
    sector_bonus: float,
    technical_score: float,
    accumulation_score: float,
    breakout_score: float,
    scoring_config: ScoringConfig,
    strategy_hash: str = "",
) -> float:
    """
    Compute and store weighted composite score for a stock.

    For now uses the same additive approach as v7 (scores are already
    on comparable scales), but with strategy_hash tagging for versioned results.
    The weighted normalization will be activated when individual scorers
    return ScoreResult with max_possible values in Phase 2+.

    Returns composite score.
    """
    # Ensure all scores are native Python floats
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

    # Upsert into scores table
    db.execute(
        text("""
            INSERT INTO scores (stock_id, date, momentum_score, fundamental_score,
                                sector_score, technical_score, accumulation_score,
                                breakout_score, composite_score, strategy_hash)
            VALUES (:stock_id, :date, :momentum, :fundamental, :sector,
                    :technical, :accumulation, :breakout, :composite, :strategy_hash)
            ON CONFLICT (stock_id, date) DO UPDATE SET
                momentum_score    = EXCLUDED.momentum_score,
                fundamental_score = EXCLUDED.fundamental_score,
                sector_score      = EXCLUDED.sector_score,
                technical_score   = EXCLUDED.technical_score,
                accumulation_score = EXCLUDED.accumulation_score,
                breakout_score    = EXCLUDED.breakout_score,
                composite_score   = EXCLUDED.composite_score,
                strategy_hash     = EXCLUDED.strategy_hash
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
            "strategy_hash": strategy_hash,
        },
    )

    return composite
