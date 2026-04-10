"""
Pairwise correlation calculator for position sizing adjustment.

Computes 60-day daily return correlation between a candidate stock and
each existing portfolio holding. Used to reduce position size when
correlation is dangerously high (momentum portfolios cluster in leading sectors).

Rationale: A 15-stock portfolio can behave like 3-4 concentrated positions
when intra-portfolio correlations spike to 0.80-0.95 during crashes.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


def compute_pairwise_correlation(
    db: Session,
    candidate_id: int,
    existing_ids: list[int],
    target_date: date,
    lookback_days: int = 60,
    min_overlap_days: int = 30,
) -> dict[int, float]:
    """
    Compute correlation of candidate stock with each existing holding.

    Returns dict mapping existing stock_id -> correlation coefficient.
    Only includes pairs with at least min_overlap_days of overlapping data.
    """
    if not existing_ids:
        return {}

    all_ids = [candidate_id] + existing_ids
    start_date = target_date - timedelta(days=int(lookback_days * 1.5))  # buffer for weekends

    # Batch load prices
    rows = db.execute(
        text("""
            SELECT stock_id, date, adj_close FROM eod_prices
            WHERE stock_id = ANY(:ids) AND date BETWEEN :start AND :end
              AND adj_close IS NOT NULL
            ORDER BY stock_id, date
        """),
        {"ids": all_ids, "start": start_date, "end": target_date},
    ).fetchall()

    if not rows:
        return {}

    # Group by stock_id -> {date: adj_close}
    price_map: dict[int, dict[date, float]] = {}
    for sid, dt, price in rows:
        if sid not in price_map:
            price_map[sid] = {}
        price_map[sid][dt] = float(price)

    candidate_prices = price_map.get(candidate_id, {})
    if len(candidate_prices) < min_overlap_days:
        return {}

    results = {}
    for existing_id in existing_ids:
        existing_prices = price_map.get(existing_id, {})

        # Find overlapping dates
        common_dates = sorted(set(candidate_prices.keys()) & set(existing_prices.keys()))

        # Take most recent lookback_days
        if len(common_dates) > lookback_days:
            common_dates = common_dates[-lookback_days:]

        if len(common_dates) < min_overlap_days:
            continue

        # Compute daily returns
        cand_prices = [candidate_prices[d] for d in common_dates]
        exist_prices = [existing_prices[d] for d in common_dates]

        cand_returns = np.diff(cand_prices) / np.array(cand_prices[:-1])
        exist_returns = np.diff(exist_prices) / np.array(exist_prices[:-1])

        if len(cand_returns) < 2:
            continue

        # Pearson correlation
        corr = np.corrcoef(cand_returns, exist_returns)[0, 1]
        if np.isnan(corr):
            continue

        results[existing_id] = round(float(corr), 4)

    return results
