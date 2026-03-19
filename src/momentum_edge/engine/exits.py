"""
Exit engine — 9 rules checked daily for every open position.

Exit rules (in priority order):
1. Initial stop: today's low < current_stop → Full exit
2. MA200 breach: adj_close < ma200 → Mandatory full exit
3. Regime exit: Bear or crash warning → Exit 20%/day for 5 days
4. Breakeven: gain >= 20% AND stop < entry → Move stop to entry price
5. Trail 40%: gain >= 40% → Trail 10% below 10-day high
6. Trail 100%: gain >= 100% → Trail 15% below 10-day high
7. Time stop: holding >= 20 days AND abs(gain) < 5% → Full exit
8. Climax: gain >= 20% in < 15 days → Sell 50%
9. Rebalance: RS rank below top 40% for 2 weeks → Exit signal
"""

from dataclasses import dataclass
from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class ExitSignal:
    stock_id: int
    symbol: str
    exit_type: str  # stop/trailing/breakeven/time/climax/regime/ma200/rebalance
    action: str  # full_exit / partial_exit_50 / move_stop / exit_20pct
    new_stop: float | None  # for trailing/breakeven moves
    reason: str


# ---------------------------------------------------------------------------
# Market data helpers
# ---------------------------------------------------------------------------


def _fetch_market_data(db: Session, stock_id: int, as_of_date: date) -> dict | None:
    """
    Fetch today's price bar, MA200, 10-day high, and RS rank for a stock.

    Returns dict with keys: adj_close, low, high, ma200, high_10d, rs_rank,
    total_ranked — or None if data is missing.
    """
    # Today's price + MA200
    row = db.execute(
        text("""
            SELECT e.adj_close, e.low, e.high, i.ma200, i.rs_rank
            FROM eod_prices e
            JOIN indicators i ON i.stock_id = e.stock_id AND i.date = e.date
            WHERE e.stock_id = :stock_id AND e.date = :as_of_date
        """),
        {"stock_id": stock_id, "as_of_date": as_of_date},
    ).fetchone()

    if row is None:
        return None

    # 10-day high
    high_10d_row = db.execute(
        text("""
            SELECT MAX(high) AS high_10d
            FROM eod_prices
            WHERE stock_id = :stock_id AND date <= :as_of_date
            ORDER BY date DESC
            LIMIT 10
        """),
        {"stock_id": stock_id, "as_of_date": as_of_date},
    ).fetchone()

    # Total ranked stocks (for RS percentile)
    total_row = db.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM indicators
            WHERE date = :as_of_date AND rs_rank IS NOT NULL
        """),
        {"as_of_date": as_of_date},
    ).fetchone()

    return {
        "adj_close": float(row.adj_close),
        "low": float(row.low),
        "high": float(row.high),
        "ma200": float(row.ma200) if row.ma200 is not None else None,
        "high_10d": float(high_10d_row.high_10d) if high_10d_row and high_10d_row.high_10d else None,
        "rs_rank": int(row.rs_rank) if row.rs_rank is not None else None,
        "total_ranked": int(total_row.cnt) if total_row else 0,
    }


# ---------------------------------------------------------------------------
# Individual exit checks (priority order)
# ---------------------------------------------------------------------------


def _check_initial_stop(position: dict, today_low: float) -> ExitSignal | None:
    """Rule 1: If today's low < current stop → full exit."""
    current_stop = position["current_stop"]
    if current_stop is not None and today_low < current_stop:
        return ExitSignal(
            stock_id=position["stock_id"],
            symbol=position["symbol"],
            exit_type="stop",
            action="full_exit",
            new_stop=None,
            reason=f"Initial stop hit: low {today_low:.2f} < stop {current_stop:.2f}",
        )
    return None


def _check_ma200_breach(position: dict, adj_close: float, ma200: float) -> ExitSignal | None:
    """Rule 2: If adj_close < MA200 → mandatory full exit."""
    if ma200 is not None and adj_close < ma200:
        return ExitSignal(
            stock_id=position["stock_id"],
            symbol=position["symbol"],
            exit_type="ma200",
            action="full_exit",
            new_stop=None,
            reason=f"MA200 breach: close {adj_close:.2f} < MA200 {ma200:.2f}",
        )
    return None


def _check_regime_exit(position: dict, regime: str, crash_warning: bool) -> ExitSignal | None:
    """Rule 3: If Bear regime or crash warning → exit 20% per day (5 days to fully exit)."""
    if regime == "Bear" or crash_warning:
        trigger = "crash warning" if crash_warning else "Bear regime"
        return ExitSignal(
            stock_id=position["stock_id"],
            symbol=position["symbol"],
            exit_type="regime",
            action="exit_20pct",
            new_stop=None,
            reason=f"Regime exit triggered: {trigger}",
        )
    return None


def _check_breakeven(position: dict, adj_close: float) -> ExitSignal | None:
    """Rule 4: If gain >= 20% and stop < entry → move stop to entry price."""
    entry_price = position["entry_price"]
    current_stop = position["current_stop"]
    gain_pct = ((adj_close - entry_price) / entry_price) * 100

    if gain_pct >= 20 and (current_stop is None or current_stop < entry_price):
        return ExitSignal(
            stock_id=position["stock_id"],
            symbol=position["symbol"],
            exit_type="breakeven",
            action="move_stop",
            new_stop=entry_price,
            reason=f"Breakeven lock: gain {gain_pct:.1f}% >= 20%, stop moved to entry {entry_price:.2f}",
        )
    return None


def _check_trailing_stop(position: dict, adj_close: float, high_10d: float) -> ExitSignal | None:
    """
    Rules 5 & 6 combined:
    - Gain >= 100% → trail 15% below 10-day high
    - Gain >= 40%  → trail 10% below 10-day high
    Higher gain threshold takes priority.
    """
    entry_price = position["entry_price"]
    current_stop = position["current_stop"]
    gain_pct = ((adj_close - entry_price) / entry_price) * 100

    if high_10d is None:
        return None

    trail_pct: float | None = None
    if gain_pct >= 100:
        trail_pct = 0.15
    elif gain_pct >= 40:
        trail_pct = 0.10

    if trail_pct is None:
        return None

    new_stop = round(high_10d * (1 - trail_pct), 2)

    # Only raise stop, never lower it
    if current_stop is not None and new_stop <= current_stop:
        return None

    return ExitSignal(
        stock_id=position["stock_id"],
        symbol=position["symbol"],
        exit_type="trailing",
        action="move_stop",
        new_stop=new_stop,
        reason=(
            f"Trailing stop: gain {gain_pct:.1f}%, "
            f"trail {trail_pct * 100:.0f}% below 10d-high {high_10d:.2f} → stop {new_stop:.2f}"
        ),
    )


def _check_time_stop(position: dict, adj_close: float, as_of_date: date) -> ExitSignal | None:
    """Rule 7: If holding >= 20 days and abs(gain) < 5% → full exit."""
    entry_price = position["entry_price"]
    entry_date = position["entry_date"]

    if isinstance(entry_date, str):
        entry_date = date.fromisoformat(entry_date)

    holding_days = (as_of_date - entry_date).days
    gain_pct = ((adj_close - entry_price) / entry_price) * 100

    if holding_days >= 20 and abs(gain_pct) < 5:
        return ExitSignal(
            stock_id=position["stock_id"],
            symbol=position["symbol"],
            exit_type="time",
            action="full_exit",
            new_stop=None,
            reason=(
                f"Time stop: {holding_days} days held, gain {gain_pct:+.1f}% "
                f"(abs < 5% threshold)"
            ),
        )
    return None


def _check_climax_exit(position: dict, adj_close: float, as_of_date: date) -> ExitSignal | None:
    """Rule 8: If gain >= 20% achieved in < 15 days → sell 50%."""
    entry_price = position["entry_price"]
    entry_date = position["entry_date"]

    if isinstance(entry_date, str):
        entry_date = date.fromisoformat(entry_date)

    holding_days = (as_of_date - entry_date).days
    gain_pct = ((adj_close - entry_price) / entry_price) * 100

    if gain_pct >= 20 and holding_days < 15:
        return ExitSignal(
            stock_id=position["stock_id"],
            symbol=position["symbol"],
            exit_type="climax",
            action="partial_exit_50",
            new_stop=None,
            reason=(
                f"Climax top: {gain_pct:.1f}% gain in {holding_days} days "
                f"(>= 20% in < 15 days)"
            ),
        )
    return None


def _check_rebalance(position: dict, rs_rank: int, total_stocks: int) -> ExitSignal | None:
    """
    Rule 9: If RS rank is below the top 40% for 2+ consecutive weeks → exit.

    Note: two-week persistence tracking requires external state. This function
    checks the single-day condition. The caller (pipeline) should track
    consecutive weeks and only act when the condition persists for 2 weeks.
    """
    if total_stocks <= 0 or rs_rank is None:
        return None

    # Top 40% means rank <= 40th percentile (rank 1 = best)
    cutoff = int(total_stocks * 0.4)
    if rs_rank > cutoff:
        return ExitSignal(
            stock_id=position["stock_id"],
            symbol=position["symbol"],
            exit_type="rebalance",
            action="full_exit",
            new_stop=None,
            reason=(
                f"Rebalance: RS rank {rs_rank}/{total_stocks} "
                f"(below top 40% cutoff of {cutoff})"
            ),
        )
    return None


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def check_exits(
    db: Session,
    open_positions: list[dict],
    as_of_date: date,
    regime: str,
    crash_warning: bool,
) -> list[ExitSignal]:
    """
    Check all 9 exit rules for each open position.

    open_positions: list of dicts with keys:
        stock_id, symbol, entry_date, entry_price, current_stop,
        shares, position_value, sector

    Returns list of ExitSignal actions to take.
    Priority: first matching rule wins per position
    (stop > MA200 > regime > breakeven > trailing > time > climax > rebalance).
    """
    signals: list[ExitSignal] = []

    for pos in open_positions:
        symbol = pos["symbol"]
        stock_id = pos["stock_id"]

        mkt = _fetch_market_data(db, stock_id, as_of_date)
        if mkt is None:
            logger.warning("No market data for {} on {} — skipping exit checks", symbol, as_of_date)
            continue

        adj_close = mkt["adj_close"]
        today_low = mkt["low"]
        ma200 = mkt["ma200"]
        high_10d = mkt["high_10d"]
        rs_rank = mkt["rs_rank"]
        total_ranked = mkt["total_ranked"]

        # Check rules in priority order — first match wins
        checks = [
            lambda: _check_initial_stop(pos, today_low),
            lambda: _check_ma200_breach(pos, adj_close, ma200),
            lambda: _check_regime_exit(pos, regime, crash_warning),
            lambda: _check_breakeven(pos, adj_close),
            lambda: _check_trailing_stop(pos, adj_close, high_10d),
            lambda: _check_time_stop(pos, adj_close, as_of_date),
            lambda: _check_climax_exit(pos, adj_close, as_of_date),
            lambda: _check_rebalance(pos, rs_rank, total_ranked),
        ]

        for check_fn in checks:
            signal = check_fn()
            if signal is not None:
                logger.info(
                    "Exit signal for {}: {} — {}",
                    symbol,
                    signal.exit_type,
                    signal.reason,
                )
                signals.append(signal)
                break

    logger.info("Exit engine: {} signals from {} positions", len(signals), len(open_positions))
    return signals
