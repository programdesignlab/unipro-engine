"""
v16 Fast Crash Detector — independent of the 3-day regime stability rule.

Trigger: Nifty index declines > 8% in any rolling 5-trading-day window.
Response: Sell 50% of every open position at next open; block all new entries.
Reset: When no 5-day window in the last 10 days shows > 8% decline.

Interaction with monster override: fast crash halves monster positions too.
Monster override flag stays True — Phase 4 rules resume after reset.

Validated: March 2020 — Nifty lost ~12% in first 5 days; regime engine
needed until day 12-16 to transition. Fast crash fires by day 5.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.core.strategy import FastCrashConfig


@dataclass
class FastCrashResult:
    is_active: bool
    sell_half_all: bool
    block_new_entries: bool
    decline_pct: float | None      # worst 5-day decline found
    reason: str


def detect_fast_crash(
    db: Session,
    target_date: date,
    config: FastCrashConfig | None = None,
) -> FastCrashResult:
    """
    Check if fast crash conditions are met.

    Reads Nifty prices from eod_prices and checks all rolling 5-day windows
    in the last `reset_lookback_days` for a decline > `decline_threshold`.
    """
    if config is None or not config.enabled:
        return FastCrashResult(
            is_active=False, sell_half_all=False, block_new_entries=False,
            decline_pct=None, reason="fast crash disabled",
        )

    window = config.rolling_window_days
    threshold = config.decline_threshold  # negative, e.g. -0.08
    reset_lookback = config.reset_lookback_days

    # Load Nifty prices
    nifty_stock = db.execute(
        text("SELECT id FROM stocks WHERE symbol IN ('NIFTY 50', '^NSEI', 'NIFTY50') LIMIT 1")
    ).fetchone()

    if not nifty_stock:
        logger.warning("[FastCrash] No Nifty 50 stock in DB — cannot detect crash")
        return FastCrashResult(
            is_active=False, sell_half_all=False, block_new_entries=False,
            decline_pct=None, reason="no Nifty data",
        )

    # Need enough days: reset_lookback + window for full rolling check
    rows = db.execute(
        text("""
            SELECT date, adj_close FROM eod_prices
            WHERE stock_id = :sid AND date <= :d
            ORDER BY date DESC
            LIMIT :n
        """),
        {"sid": nifty_stock[0], "d": target_date, "n": reset_lookback + window},
    ).fetchall()

    if len(rows) < window + 1:
        return FastCrashResult(
            is_active=False, sell_half_all=False, block_new_entries=False,
            decline_pct=None, reason=f"insufficient Nifty data ({len(rows)} days)",
        )

    # Rows are in DESC order — reverse for chronological
    prices = list(reversed([(r[0], float(r[1])) for r in rows]))

    # Check all rolling windows
    worst_decline = 0.0
    crash_detected = False

    for i in range(len(prices) - window):
        start_price = prices[i][1]
        end_price = prices[i + window][1]
        decline = (end_price - start_price) / start_price

        if decline < worst_decline:
            worst_decline = decline

        if decline < threshold:
            crash_detected = True

    if crash_detected:
        logger.warning(
            "[FastCrash] ACTIVE — worst {}-day decline: {:.2f}% (threshold: {:.0f}%)",
            window, worst_decline * 100, threshold * 100,
        )
        return FastCrashResult(
            is_active=True,
            sell_half_all=True,
            block_new_entries=True,
            decline_pct=worst_decline,
            reason=f"Nifty {window}-day decline {worst_decline*100:.1f}% breached {threshold*100:.0f}% threshold",
        )

    return FastCrashResult(
        is_active=False, sell_half_all=False, block_new_entries=False,
        decline_pct=worst_decline,
        reason=f"no crash — worst {window}-day decline: {worst_decline*100:.1f}%",
    )
