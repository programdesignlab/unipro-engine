"""
Signals engine — manages the Pending -> Confirmed/Failed/Expired lifecycle.

Day 1: breakout detected -> signal created as Pending
Day 2: check if price held above pivot -> Confirmed or Failed
Next-day open > pivot + 3% -> Expired (gap too large to enter)
Earnings within 10 days -> auto-downgrade to Tier 3
"""

from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.models import EODPrice, Signal


# ---------------------------------------------------------------------------
# Tier thresholds
# ---------------------------------------------------------------------------
_TIER1_REGIMES = {"Bull", "StrongBull"}
_TIER1_SCORE_MIN = 75.0
_TIER2_PROXIMITY_PCT = 0.03  # within 3% of pivot
_TIER2_SCORE_MIN = 65.0
_TIER3_SCORE_MIN = 55.0

_GAP_LIMIT_PCT = 0.03  # open > pivot * 1.03 -> Expired
_EARNINGS_WINDOW_DAYS = 10


# ---------------------------------------------------------------------------
# Tier assignment
# ---------------------------------------------------------------------------

def _assign_tier(
    pattern_type: str | None,
    regime: str | None,
    composite_score: float,
    earnings_flag: bool,
) -> int:
    """
    Determine signal tier:
      Tier 1 — confirmed breakout + bullish regime + score > 75
      Tier 2 — within 3% of pivot + score > 65
      Tier 3 — score > 55 OR earnings within 10 days (auto-downgrade)
    Earnings within 10 days forces Tier 3 regardless of other criteria.
    """
    if earnings_flag:
        return 3

    if (
        pattern_type is not None
        and regime in _TIER1_REGIMES
        and composite_score >= _TIER1_SCORE_MIN
    ):
        return 1

    if composite_score >= _TIER2_SCORE_MIN:
        return 2

    if composite_score >= _TIER3_SCORE_MIN:
        return 3

    # Below all thresholds — still create the signal as Tier 3
    return 3


# ---------------------------------------------------------------------------
# create_signal
# ---------------------------------------------------------------------------

def create_signal(
    db: Session,
    stock_id: int,
    target_date: date,
    pattern_result,
    regime: str,
    crash_warning: bool,
    composite_score: float,
    vol_scalar: float,
    fundamental_bonus: int,
    *,
    earnings_date: date | None = None,
    days_to_earnings: int | None = None,
    adl_ratio: float | None = None,
    inst_flow_signal: str | None = None,
    inst_flow_positive: bool | None = None,
) -> int | None:
    """
    Create a new Pending signal from a breakout detection.

    Only creates if pattern_result has a valid pattern and entry_valid=True.
    Returns signal ID or None.
    """
    if pattern_result.pattern_type is None or not pattern_result.entry_valid:
        logger.debug(
            "Skipping signal for stock_id={} — pattern_type={}, entry_valid={}, reason={}",
            stock_id,
            pattern_result.pattern_type,
            pattern_result.entry_valid,
            pattern_result.entry_fail_reason,
        )
        return None

    earnings_flag = (
        days_to_earnings is not None and days_to_earnings <= _EARNINGS_WINDOW_DAYS
    )

    tier = _assign_tier(
        pattern_result.pattern_type, regime, composite_score, earnings_flag
    )

    signal = Signal(
        signal_date=target_date,
        stock_id=stock_id,
        pattern_type=pattern_result.pattern_type,
        status="Pending",
        pivot_price=pattern_result.pivot_price,
        stop_loss=pattern_result.stop_loss_level,
        entry_zone_low=pattern_result.entry_zone_low,
        entry_zone_high=pattern_result.entry_zone_high,
        volume_ratio=pattern_result.volume_ratio,
        obv_slope=pattern_result.obv_slope,
        obv_bonus=pattern_result.obv_bonus,
        obv_divergence=pattern_result.obv_divergence,
        adl_ratio=adl_ratio,
        inst_flow_signal=inst_flow_signal,
        inst_flow_positive=inst_flow_positive,
        base_length_days=pattern_result.base_length_days,
        base_depth_pct=pattern_result.base_depth_pct,
        regime=regime,
        crash_warning=crash_warning,
        earnings_date=earnings_date,
        days_to_earnings=days_to_earnings,
        earnings_flag=earnings_flag,
        tier=tier,
        composite_score=composite_score,
        vol_scalar=vol_scalar,
        fundamental_bonus=fundamental_bonus,
    )

    db.add(signal)
    db.flush()  # populate signal.id without committing

    logger.info(
        "Created Pending signal id={} stock_id={} pattern={} tier={} score={:.1f}",
        signal.id,
        stock_id,
        pattern_result.pattern_type,
        tier,
        composite_score,
    )
    return signal.id


# ---------------------------------------------------------------------------
# update_pending_signals
# ---------------------------------------------------------------------------

def update_pending_signals(db: Session, as_of_date: date) -> dict:
    """
    Check all Pending signals from previous days.

    For each pending signal:
      1. Fetch today's open and adj_close (fallback to close) for the stock.
      2. If open > pivot * 1.03  -> Expired  (gap too large to enter)
      3. If adj_close > pivot   -> Confirmed (set confirmed_date)
      4. If adj_close <= pivot  -> Failed    (set failed_date)

    Returns dict with counts: {'confirmed': N, 'failed': N, 'expired': N}
    """
    counts = {"confirmed": 0, "failed": 0, "expired": 0}

    pending_signals: list[Signal] = (
        db.query(Signal)
        .filter(Signal.status == "Pending", Signal.signal_date < as_of_date)
        .all()
    )

    if not pending_signals:
        logger.debug("No pending signals to update as of {}", as_of_date)
        return counts

    # Batch-fetch today's prices for all relevant stock_ids
    stock_ids = [s.stock_id for s in pending_signals]
    prices: list[EODPrice] = (
        db.query(EODPrice)
        .filter(EODPrice.stock_id.in_(stock_ids), EODPrice.date == as_of_date)
        .all()
    )
    price_map: dict[int, EODPrice] = {p.stock_id: p for p in prices}

    for sig in pending_signals:
        price = price_map.get(sig.stock_id)
        if price is None:
            logger.warning(
                "No price data for stock_id={} on {} — signal id={} stays Pending",
                sig.stock_id,
                as_of_date,
                sig.id,
            )
            continue

        pivot = sig.pivot_price
        if pivot is None:
            logger.warning("Signal id={} has no pivot_price — skipping", sig.id)
            continue

        today_open = price.open
        today_close = price.adj_close if price.adj_close is not None else price.close

        # Rule 1: gap too large
        if today_open > pivot * (1 + _GAP_LIMIT_PCT):
            sig.status = "Expired"
            logger.info(
                "Signal id={} Expired — open {:.2f} > pivot {:.2f} + 3%",
                sig.id,
                today_open,
                pivot,
            )
            counts["expired"] += 1

        # Rule 2: price held above pivot
        elif today_close > pivot:
            sig.status = "Confirmed"
            sig.confirmed_date = as_of_date
            logger.info(
                "Signal id={} Confirmed — close {:.2f} > pivot {:.2f}",
                sig.id,
                today_close,
                pivot,
            )
            counts["confirmed"] += 1

        # Rule 3: price fell below pivot
        else:
            sig.status = "Failed"
            sig.failed_date = as_of_date
            logger.info(
                "Signal id={} Failed — close {:.2f} <= pivot {:.2f}",
                sig.id,
                today_close,
                pivot,
            )
            counts["failed"] += 1

    db.flush()

    logger.info(
        "Pending signal update complete: {} confirmed, {} failed, {} expired",
        counts["confirmed"],
        counts["failed"],
        counts["expired"],
    )
    return counts


# ---------------------------------------------------------------------------
# get_active_signals
# ---------------------------------------------------------------------------

def get_active_signals(db: Session, as_of_date: date) -> list[dict]:
    """
    Get all Confirmed signals that haven't been superseded.

    A signal is superseded if a newer Confirmed signal exists for the same
    stock_id. Only the most recent confirmed signal per stock is returned.

    Returns list of signal dicts for watchlist generation.
    """
    # Subquery: latest confirmed signal per stock
    latest_sq = (
        db.query(
            Signal.stock_id,
            db.query(Signal.id)
            .filter(
                Signal.stock_id == Signal.stock_id,
                Signal.status == "Confirmed",
                Signal.confirmed_date <= as_of_date,
            )
            .order_by(Signal.confirmed_date.desc())
            .limit(1)
            .correlate(Signal)
            .scalar_subquery()
            .label("latest_id"),
        )
        .filter(Signal.status == "Confirmed", Signal.confirmed_date <= as_of_date)
        .distinct()
        .subquery()
    )

    # Use raw SQL for clarity — get the latest confirmed signal per stock
    stmt = text("""
        SELECT s.*
        FROM signals s
        INNER JOIN (
            SELECT stock_id, MAX(confirmed_date) AS max_confirmed
            FROM signals
            WHERE status = 'Confirmed'
              AND confirmed_date <= :as_of
            GROUP BY stock_id
        ) latest ON s.stock_id = latest.stock_id
                 AND s.confirmed_date = latest.max_confirmed
        WHERE s.status = 'Confirmed'
        ORDER BY s.composite_score DESC NULLS LAST
    """)

    rows = db.execute(stmt, {"as_of": as_of_date}).mappings().all()

    results = []
    for row in rows:
        results.append(
            {
                "signal_id": row["id"],
                "stock_id": row["stock_id"],
                "signal_date": row["signal_date"],
                "confirmed_date": row["confirmed_date"],
                "pattern_type": row["pattern_type"],
                "tier": row["tier"],
                "composite_score": row["composite_score"],
                "pivot_price": row["pivot_price"],
                "stop_loss": row["stop_loss"],
                "entry_zone_low": row["entry_zone_low"],
                "entry_zone_high": row["entry_zone_high"],
                "volume_ratio": row["volume_ratio"],
                "regime": row["regime"],
                "crash_warning": row["crash_warning"],
                "earnings_flag": row["earnings_flag"],
                "days_to_earnings": row["days_to_earnings"],
                "vol_scalar": row["vol_scalar"],
                "fundamental_bonus": row["fundamental_bonus"],
            }
        )

    logger.info("Active confirmed signals as of {}: {}", as_of_date, len(results))
    return results
