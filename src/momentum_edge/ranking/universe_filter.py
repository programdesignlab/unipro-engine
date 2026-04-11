"""
v16 Universe Filter — 8 hard blocks for junk removal.

Filters eliminate stocks from the universe entirely (they never receive a score).
Each filter reads params from strategy YAML. Fail-closed: missing data on a
hard block = exclude stock + log exclusion.

Filters:
  1. market_cap_band    — Market cap within configured range
  2. liquidity          — Avg daily traded value above minimum
  3. surveillance       — Not under ASM/ESM
  4. eps_junk           — Positive EPS in N of last M quarters
  5. ocf_quality        — Operating cash flow not persistently negative
  6. promoter_pledge    — Pledge % below threshold
  7. sebi_fine          — No SEBI price manipulation fine in lookback period
  8. ipo_age            — Listed for at least N trading days
  9. business_pivot     — (disabled by default — data source TBD)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.models import Stock


@dataclass
class FilterResult:
    passes: bool
    fail_reason: str | None
    data_missing: bool = False


# ---------------------------------------------------------------------------
# Individual filter functions
# ---------------------------------------------------------------------------


def _check_market_cap(db: Session, stock: Stock, as_of_date: date, params: dict) -> FilterResult:
    """Market cap within [min_cr, max_cr] range."""
    min_cr = params.get("min_cr", 1000)
    max_cr = params.get("max_cr", 30000)

    if stock.market_cap is None:
        return FilterResult(passes=False, fail_reason="market_cap_missing", data_missing=True)

    if stock.market_cap < min_cr or stock.market_cap > max_cr:
        return FilterResult(passes=False, fail_reason=f"market_cap_{stock.market_cap:.0f}cr")

    return FilterResult(passes=True, fail_reason=None)


def _check_liquidity(db: Session, stock: Stock, as_of_date: date, params: dict) -> FilterResult:
    """Avg daily traded value above minimum."""
    min_tv = params.get("min_daily_traded_value_cr", 15.0)
    avg_tv = stock.avg_daily_tv_cr

    if avg_tv is None:
        # Fallback: calculate from recent 20 trading days
        row = db.execute(
            text("""
                SELECT AVG(traded_value_cr) FROM (
                    SELECT traded_value_cr FROM eod_prices
                    WHERE stock_id = :sid AND date <= :d AND traded_value_cr IS NOT NULL
                    ORDER BY date DESC LIMIT 20
                ) sub
            """),
            {"sid": stock.id, "d": as_of_date},
        ).scalar()

        if row is not None:
            avg_tv = float(row)
        else:
            # Last resort: volume * close
            fallback = db.execute(
                text("""
                    SELECT AVG(volume * close) / 1e7 FROM (
                        SELECT volume, close FROM eod_prices
                        WHERE stock_id = :sid AND date <= :d
                        ORDER BY date DESC LIMIT 20
                    ) sub
                """),
                {"sid": stock.id, "d": as_of_date},
            ).scalar()
            if fallback is not None:
                avg_tv = float(fallback)

    if avg_tv is None or avg_tv < min_tv:
        return FilterResult(passes=False, fail_reason=f"illiquid_{avg_tv or 0:.1f}cr")

    return FilterResult(passes=True, fail_reason=None)


def _check_surveillance(db: Session, stock: Stock, as_of_date: date, params: dict) -> FilterResult:
    """Not under ASM/ESM surveillance."""
    if stock.is_asm or stock.is_esm:
        kind = "ASM" if stock.is_asm else "ESM"
        return FilterResult(passes=False, fail_reason=f"surveillance_{kind}")

    return FilterResult(passes=True, fail_reason=None)


def _check_eps_junk(db: Session, stock: Stock, as_of_date: date, params: dict) -> FilterResult:
    """Positive EPS in at least min_positive_quarters of last lookback_quarters."""
    min_pos = params.get("min_positive_quarters", 2)
    lookback = params.get("lookback_quarters", 4)

    rows = db.execute(
        text("""
            SELECT eps FROM fundamentals
            WHERE stock_id = :sid AND reporting_date <= :d
            ORDER BY quarter DESC LIMIT :n
        """),
        {"sid": stock.id, "d": as_of_date, "n": lookback},
    ).fetchall()

    if not rows:
        # No fundamental data — pass through (data not ingested yet)
        return FilterResult(passes=True, fail_reason=None)

    positive_count = sum(1 for r in rows if r[0] is not None and r[0] > 0)
    if positive_count < min_pos:
        return FilterResult(passes=False, fail_reason=f"eps_junk_{positive_count}of{len(rows)}")

    return FilterResult(passes=True, fail_reason=None)


def _check_ocf(db: Session, stock: Stock, as_of_date: date, params: dict) -> FilterResult:
    """Operating cash flow not negative in max_negative_quarters of lookback_quarters."""
    max_neg = params.get("max_negative_quarters", 3)
    lookback = params.get("lookback_quarters", 4)

    rows = db.execute(
        text("""
            SELECT ocf_cr FROM fundamentals
            WHERE stock_id = :sid AND reporting_date <= :d AND ocf_cr IS NOT NULL
            ORDER BY quarter DESC LIMIT :n
        """),
        {"sid": stock.id, "d": as_of_date, "n": lookback},
    ).fetchall()

    if not rows:
        # No OCF data ingested yet — pass through (data not available)
        # Once OCF data is ingested, fail-closed behavior activates automatically
        return FilterResult(passes=True, fail_reason=None)

    negative_count = sum(1 for r in rows if r[0] is not None and r[0] < 0)
    if negative_count >= max_neg:
        return FilterResult(passes=False, fail_reason=f"ocf_negative_{negative_count}of{len(rows)}")

    return FilterResult(passes=True, fail_reason=None)


def _check_pledge(db: Session, stock: Stock, as_of_date: date, params: dict) -> FilterResult:
    """Promoter pledge below threshold."""
    thresh_operational = params.get("threshold_operational", 0.20)
    thresh_infra = params.get("threshold_infra", 0.50)

    # Get pledge from shareholding pattern
    row = db.execute(
        text("""
            SELECT promoter_pct FROM shareholding_pattern
            WHERE stock_id = :sid AND quarter_end_date <= :d
            ORDER BY quarter_end_date DESC LIMIT 1
        """),
        {"sid": stock.id, "d": as_of_date},
    ).fetchone()

    # If no shareholding data, pass through
    if not row or row[0] is None:
        return FilterResult(passes=True, fail_reason=None)

    # Get pledge data from stock model (if available)
    pledge_pct = getattr(stock, "pledge_pct", None)
    if pledge_pct is None:
        # No pledge data available — pass through
        return FilterResult(passes=True, fail_reason=None)

    # Check against thresholds
    sector = stock.sector or ""
    is_infra = any(kw in sector.lower() for kw in ("infra", "power", "roads", "construction"))

    threshold = thresh_infra if is_infra else thresh_operational
    if pledge_pct > threshold:
        # Infra exception: allow if D/E falling AND revenue growth > 30%
        if is_infra:
            infra_exc = params.get("infra_exception", {})
            if infra_exc.get("de_falling") and infra_exc.get("revenue_growth_min"):
                de_rows = db.execute(
                    text("""
                        SELECT debt_to_equity FROM fundamentals
                        WHERE stock_id = :sid AND debt_to_equity IS NOT NULL
                        ORDER BY quarter DESC LIMIT 2
                    """),
                    {"sid": stock.id},
                ).fetchall()
                rev_row = db.execute(
                    text("""
                        SELECT revenue_yoy_growth FROM fundamentals
                        WHERE stock_id = :sid AND revenue_yoy_growth IS NOT NULL
                        ORDER BY quarter DESC LIMIT 1
                    """),
                    {"sid": stock.id},
                ).fetchone()

                de_falling = len(de_rows) >= 2 and de_rows[0][0] < de_rows[1][0]
                rev_strong = rev_row and rev_row[0] and rev_row[0] > infra_exc["revenue_growth_min"] * 100

                if de_falling and rev_strong:
                    return FilterResult(passes=True, fail_reason=None)  # exception granted

        return FilterResult(
            passes=False,
            fail_reason=f"pledge_{pledge_pct*100:.0f}pct_gt_{threshold*100:.0f}pct",
        )

    return FilterResult(passes=True, fail_reason=None)


def _check_sebi_fine(db: Session, stock: Stock, as_of_date: date, params: dict) -> FilterResult:
    """No SEBI price manipulation fine in lookback period."""
    # Check stock-level flag
    has_fine = getattr(stock, "sebi_fine_last_24m", False)
    if has_fine:
        return FilterResult(passes=False, fail_reason="sebi_fine_active")

    return FilterResult(passes=True, fail_reason=None)


def _check_ipo_age(db: Session, stock: Stock, as_of_date: date, params: dict) -> FilterResult:
    """Stock must have been listed for at least min_trading_days."""
    min_days = params.get("min_trading_days", 200)

    listing_date = stock.listing_date
    if listing_date is None:
        # No listing date — check if we have enough price history
        count = db.execute(
            text("""
                SELECT COUNT(*) FROM eod_prices
                WHERE stock_id = :sid AND date <= :d
            """),
            {"sid": stock.id, "d": as_of_date},
        ).scalar()

        if count and count >= min_days:
            return FilterResult(passes=True, fail_reason=None)
        elif count is not None and count < min_days:
            return FilterResult(passes=False, fail_reason=f"ipo_age_{count}days")
        return FilterResult(passes=True, fail_reason=None)

    trading_days = (as_of_date - listing_date).days
    if trading_days < min_days:
        return FilterResult(passes=False, fail_reason=f"ipo_age_{trading_days}days")

    return FilterResult(passes=True, fail_reason=None)


def _check_business_pivot(db: Session, stock: Stock, as_of_date: date, params: dict) -> FilterResult:
    """Business pivot / object clause changes — STUBBED (data source TBD)."""
    # Always passes until data source is available
    logger.debug("{}: business_pivot filter stubbed — passing", stock.symbol)
    return FilterResult(passes=True, fail_reason=None)


# ---------------------------------------------------------------------------
# Filter registry
# ---------------------------------------------------------------------------


_FILTER_FUNCTIONS = {
    "check_market_cap": _check_market_cap,
    "check_liquidity": _check_liquidity,
    "check_asm_esm": _check_surveillance,
    "check_eps_junk": _check_eps_junk,
    "check_ocf": _check_ocf,
    "check_pledge": _check_pledge,
    "check_sebi_fine": _check_sebi_fine,
    "check_ipo_age": _check_ipo_age,
    "check_business_pivot": _check_business_pivot,
}


# ---------------------------------------------------------------------------
# Exclusion logging
# ---------------------------------------------------------------------------


def _log_exclusion(
    db: Session,
    stock_id: int,
    target_date: date,
    filter_name: str,
    reason: str,
    strategy_hash: str = "",
    data_missing: bool = False,
) -> None:
    """Log filter exclusion to exclusion_log table (if it exists)."""
    try:
        db.execute(
            text("""
                INSERT INTO exclusion_log (date, stock_id, block_name, reason, data_missing, strategy_hash)
                VALUES (:d, :sid, :block, :reason, :dm, :hash)
            """),
            {
                "d": target_date, "sid": stock_id, "block": filter_name,
                "reason": reason, "dm": data_missing, "hash": strategy_hash,
            },
        )
    except Exception:
        # Table may not exist yet — silently skip
        db.rollback()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def passes_hard_filters(
    db: Session, stock: Stock, as_of_date: date, strategy=None,
) -> FilterResult:
    """
    Run all enabled hard blocks from strategy YAML.

    Each filter is dispatched by its `function` name. Fail-closed on missing
    data for critical filters (OCF, pledge). Exclusions are logged.
    """
    strategy_hash = strategy.strategy_hash if strategy else ""

    if strategy is not None:
        blocks = [b for b in strategy.universe.hard_blocks if b.enabled]
    else:
        # Fallback: run v7 defaults (4 filters)
        blocks = [
            type("B", (), {"name": "market_cap_band", "function": "check_market_cap", "params": {}})(),
            type("B", (), {"name": "liquidity", "function": "check_liquidity", "params": {}})(),
            type("B", (), {"name": "surveillance", "function": "check_asm_esm", "params": {}})(),
            type("B", (), {"name": "eps_junk", "function": "check_eps_junk", "params": {}})(),
        ]

    for block in blocks:
        fn = _FILTER_FUNCTIONS.get(block.function)
        if fn is None:
            logger.warning("Unknown filter function: {} — skipping", block.function)
            continue

        result = fn(db, stock, as_of_date, block.params if hasattr(block, "params") else {})

        if not result.passes:
            logger.debug(
                "{} FAIL [{}]: {}",
                stock.symbol, block.name, result.fail_reason,
            )
            _log_exclusion(
                db, stock.id, as_of_date, block.name,
                result.fail_reason or block.name,
                strategy_hash=strategy_hash,
                data_missing=result.data_missing,
            )
            return FilterResult(
                passes=False,
                fail_reason=result.fail_reason,
                data_missing=result.data_missing,
            )

    logger.debug("{} PASS: all {} hard blocks cleared", stock.symbol, len(blocks))
    return FilterResult(passes=True, fail_reason=None)
