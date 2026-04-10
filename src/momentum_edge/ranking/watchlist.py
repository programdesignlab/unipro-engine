"""
M10 — Watchlist Generation.

Generates and persists the daily ranked watchlist from scored stocks.
Applies regime-based filtering:
  - Bull: full watchlist
  - Neutral: top 50% of scores only
  - Bear: cash recommended (empty or minimal watchlist)
"""

from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


def generate_watchlist(
    db: Session,
    target_date: date,
    regime: str,
    sector_ranks: list | None = None,
    strategy=None,
) -> int:
    """
    Generate watchlist from scores table for target_date.
    Applies regime-based filtering and writes to watchlist table.
    Returns count of stocks added to watchlist.
    """
    # Build sector lookup
    sector_rank_map = {}
    if sector_ranks:
        for sr in sector_ranks:
            sector_rank_map[sr.sector_name] = sr.rank

    # Get all scored stocks for the date, ordered by composite score
    rows = db.execute(
        text("""
            SELECT s.id, s.symbol, s.sector,
                   sc.composite_score, sc.breakout_score
            FROM scores sc
            JOIN stocks s ON s.id = sc.stock_id
            WHERE sc.date = :target_date AND s.is_active = true
                  AND sc.composite_score IS NOT NULL
            ORDER BY sc.composite_score DESC
        """),
        {"target_date": target_date},
    ).fetchall()

    if not rows:
        logger.warning("[M10] No scored stocks for watchlist")
        return 0

    # Regime filter
    if regime == "Bear":
        # Defensive: only top 5 stocks (or none)
        rows = rows[:5]
        logger.info("[M10] Bear regime — limiting to top 5 stocks")
    elif regime == "Neutral":
        # Moderate: top 50%
        cutoff = max(1, len(rows) // 2)
        rows = rows[:cutoff]
        logger.info(f"[M10] Neutral regime — limiting to top {cutoff} stocks")
    # Bull: full list

    # Get pattern types and stop-loss from breakout detection
    # (stored during M8 in the pipeline context, or re-query if needed)

    # Get stop-loss levels from recent price data
    watchlist_rows = []
    for rank, row in enumerate(rows, 1):
        stock_id, symbol, sector, composite, breakout = row

        # Get pattern info from breakout score context
        pattern_row = db.execute(
            text("""
                SELECT low FROM eod_prices
                WHERE stock_id = :stock_id AND date <= :target_date
                ORDER BY date DESC LIMIT 20
            """),
            {"stock_id": stock_id, "target_date": target_date},
        ).fetchall()

        # Stop loss = lowest low of last 20 days
        stop_loss = min(r[0] for r in pattern_row) if pattern_row else None

        sector_rank = sector_rank_map.get(sector)

        # Determine pattern type based on breakout score
        if breakout and breakout >= 9:
            pattern_type = "VCP"
        elif breakout and breakout >= 7:
            pattern_type = "Base"
        elif breakout and breakout >= 5:
            pattern_type = "Breakout"
        else:
            pattern_type = None

        watchlist_rows.append({
            "date": target_date,
            "stock_id": stock_id,
            "composite_score": composite,
            "rank": rank,
            "pattern_type": pattern_type,
            "regime": regime,
            "stop_loss_level": round(stop_loss, 2) if stop_loss else None,
            "sector_name": sector,
            "sector_rank": sector_rank,
        })

    if not watchlist_rows:
        return 0

    # Clear existing watchlist for this date
    db.execute(
        text("DELETE FROM watchlist WHERE date = :target_date"),
        {"target_date": target_date},
    )

    # Insert new watchlist
    db.execute(
        text("""
            INSERT INTO watchlist (date, stock_id, composite_score, rank,
                                   pattern_type, regime, stop_loss_level,
                                   sector_name, sector_rank)
            VALUES (:date, :stock_id, :composite_score, :rank,
                    :pattern_type, :regime, :stop_loss_level,
                    :sector_name, :sector_rank)
        """),
        watchlist_rows,
    )
    db.commit()

    logger.info(f"[M10] Watchlist generated: {len(watchlist_rows)} stocks ({regime} regime)")
    return len(watchlist_rows)
