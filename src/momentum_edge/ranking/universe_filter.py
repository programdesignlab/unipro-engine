"""
v7 Universe Filter — 4 hard filters for junk removal.

Replaces the old CANSLIM hard filters. These filters eliminate stocks from the
universe entirely (they never receive a score). Fundamentals are handled
separately as bonus points in fundamental_bonus.py.

Filters:
  1. Market cap 2,000–30,000 crore
  2. Avg daily traded value >= Rs.15 crore
  3. Not under ASM/ESM surveillance
  4. Positive EPS in at least 2 of the last 4 reported quarters
"""

from dataclasses import dataclass
from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.models import Stock


@dataclass
class FilterResult:
    passes: bool
    fail_reason: str | None  # market_cap, illiquid, surveillance, persistent_loss_maker


def passes_hard_filters(db: Session, stock: Stock, as_of_date: date) -> FilterResult:
    """
    4 hard filters (junk removal only — NOT CANSLIM):
    1. Market cap 2,000-30,000 crore
    2. Avg daily traded value >= Rs.15 crore
    3. Not under ASM/ESM surveillance
    4. Positive EPS in 2 of last 4 reported quarters (by reporting_date <= as_of_date)
    """

    # ── Filter 1: Market cap band ──────────────────────────────────────
    if stock.market_cap is None:
        logger.debug("{} FAIL: market_cap is NULL", stock.symbol)
        return FilterResult(passes=False, fail_reason="market_cap")

    if stock.market_cap < 2_000 or stock.market_cap > 30_000:
        logger.debug(
            "{} FAIL: market_cap {:.0f} cr outside 2,000–30,000 range",
            stock.symbol,
            stock.market_cap,
        )
        return FilterResult(passes=False, fail_reason="market_cap")

    # ── Filter 2: Liquidity — avg daily traded value ───────────────────
    avg_tv = stock.avg_daily_tv_cr

    if avg_tv is None:
        # Fallback: calculate from recent 20 trading days of EOD data
        row = db.execute(
            text("""
                SELECT AVG(traded_value_cr)
                FROM (
                    SELECT traded_value_cr
                    FROM eod_prices
                    WHERE stock_id = :stock_id
                      AND date <= :as_of_date
                      AND traded_value_cr IS NOT NULL
                    ORDER BY date DESC
                    LIMIT 20
                ) sub
            """),
            {"stock_id": stock.id, "as_of_date": as_of_date},
        ).scalar()

        if row is not None:
            avg_tv = float(row)
        else:
            # Last resort: estimate from volume * close
            fallback = db.execute(
                text("""
                    SELECT AVG(volume * close) / 1e7
                    FROM (
                        SELECT volume, close
                        FROM eod_prices
                        WHERE stock_id = :stock_id
                          AND date <= :as_of_date
                        ORDER BY date DESC
                        LIMIT 20
                    ) sub
                """),
                {"stock_id": stock.id, "as_of_date": as_of_date},
            ).scalar()

            if fallback is not None:
                avg_tv = float(fallback)

    if avg_tv is None or avg_tv < 15.0:
        logger.debug(
            "{} FAIL: avg daily traded value {:.2f} cr < 15 cr",
            stock.symbol,
            avg_tv if avg_tv is not None else 0.0,
        )
        return FilterResult(passes=False, fail_reason="illiquid")

    # ── Filter 3: ASM / ESM surveillance ───────────────────────────────
    if stock.is_asm or stock.is_esm:
        logger.debug(
            "{} FAIL: under surveillance (ASM={}, ESM={})",
            stock.symbol,
            stock.is_asm,
            stock.is_esm,
        )
        return FilterResult(passes=False, fail_reason="surveillance")

    # ── Filter 4: Persistent loss-maker check ──────────────────────────
    rows = db.execute(
        text("""
            SELECT eps
            FROM fundamentals
            WHERE stock_id = :stock_id
              AND reporting_date <= :as_of_date
            ORDER BY quarter DESC
            LIMIT 4
        """),
        {"stock_id": stock.id, "as_of_date": as_of_date},
    ).fetchall()

    if rows:
        positive_count = sum(1 for r in rows if r[0] is not None and r[0] > 0)
        if positive_count < 2:
            logger.debug(
                "{} FAIL: only {}/{} quarters with positive EPS",
                stock.symbol,
                positive_count,
                len(rows),
            )
            return FilterResult(passes=False, fail_reason="persistent_loss_maker")
    # If no fundamental rows exist, do NOT eliminate — let the stock through
    # (data may simply not be ingested yet).

    logger.debug("{} PASS: all 4 hard filters cleared", stock.symbol)
    return FilterResult(passes=True, fail_reason=None)
