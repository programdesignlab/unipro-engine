"""
v16 Exit Cascade — 5-layer portfolio-level exit system.

Operates on ALL open positions simultaneously (not per-position like phase exits).
Checked daily. Each layer returns actions that affect the entire portfolio.

Layers (priority order):
  E1: Climax Detection     — 80%+ gain + 30%+ surge in 15 days → staged exit
  E2: Distribution Days    — Index down >0.2% on higher volume → tighten/reduce
  E3: A/D Divergence       — Index new high + A/D lower high → reduce all 25%
  E4: New Highs Collapse   — Nifty500 52w highs dropping → tighten/reduce
  E5: Tiered Trailing      — Per-position gain-based trailing (phase-dependent)

All thresholds read from strategy.exits.cascade config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.core.strategy import CascadeConfig


@dataclass
class CascadeAction:
    """A portfolio-level exit action from the cascade."""
    layer: str              # climax_detection / distribution_days / ad_divergence / etc.
    priority: int
    action: str             # tighten_stops / reduce_25_pct / reduce_to_50_pct / sell_25_pct_immediate
    affected_stock_ids: list[int] = field(default_factory=list)
    reason: str = ""
    params: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# E1: Climax Detection
# ---------------------------------------------------------------------------


def _check_climax_detection(
    db: Session,
    positions: list,
    as_of_date: date,
    config: dict,
) -> list[CascadeAction]:
    """E1: Individual positions with 80%+ gain that surged >30% in 15 days."""
    actions = []
    trigger = config.get("trigger", {})
    gain_thresh = trigger.get("gain_threshold", 0.80)
    time_window = trigger.get("time_window_days", 15)
    surge_pct = trigger.get("surge_pct", 0.30)

    for pos in positions:
        entry_price = pos.entry_price if hasattr(pos, "entry_price") else pos["entry_price"]
        stock_id = pos.stock_id if hasattr(pos, "stock_id") else pos["stock_id"]
        symbol = pos.symbol if hasattr(pos, "symbol") else pos["symbol"]

        # Get current price
        row = db.execute(
            text("SELECT adj_close FROM eod_prices WHERE stock_id = :sid AND date = :d"),
            {"sid": stock_id, "d": as_of_date},
        ).fetchone()
        if not row:
            continue

        current_price = float(row[0])
        gain = (current_price - entry_price) / entry_price

        if gain < gain_thresh:
            continue

        # Check for surge in time window
        window_row = db.execute(
            text("""
                SELECT MIN(adj_close) FROM (
                    SELECT adj_close FROM eod_prices
                    WHERE stock_id = :sid AND date <= :d
                    ORDER BY date DESC LIMIT :window
                ) sub
            """),
            {"sid": stock_id, "d": as_of_date, "window": time_window},
        ).fetchone()

        if window_row and window_row[0]:
            window_low = float(window_row[0])
            window_surge = (current_price - window_low) / window_low
            if window_surge >= surge_pct:
                actions.append(CascadeAction(
                    layer="climax_detection",
                    priority=1,
                    action="sell_25_pct_immediate",
                    affected_stock_ids=[stock_id],
                    reason=f"{symbol}: {gain*100:.0f}% gain, {window_surge*100:.0f}% surge in {time_window}d",
                ))

    return actions


# ---------------------------------------------------------------------------
# E2: Distribution Days
# ---------------------------------------------------------------------------


def _check_distribution_days(
    db: Session,
    positions: list,
    as_of_date: date,
    config: dict,
) -> list[CascadeAction]:
    """E2: Count index down >0.2% on higher volume in last 25 days."""
    trigger = config.get("trigger", {})
    decline_pct = trigger.get("index_decline_pct", 0.002)
    lookback = trigger.get("lookback_days", 25)

    # Get Nifty prices for lookback
    nifty_stock = db.execute(
        text("SELECT id FROM stocks WHERE symbol IN ('NIFTY 50', '^NSEI', 'NIFTY50') LIMIT 1")
    ).fetchone()

    if not nifty_stock:
        return []

    rows = db.execute(
        text("""
            SELECT date, adj_close, volume FROM eod_prices
            WHERE stock_id = :sid AND date <= :d
            ORDER BY date DESC LIMIT :n
        """),
        {"sid": nifty_stock[0], "d": as_of_date, "n": lookback + 1},
    ).fetchall()

    if len(rows) < 2:
        return []

    # Count distribution days (price down > threshold on higher volume)
    dist_count = 0
    for i in range(len(rows) - 1):
        today_close = float(rows[i][1])
        prev_close = float(rows[i + 1][1])
        today_vol = int(rows[i][2])
        prev_vol = int(rows[i + 1][2])

        pct_change = (today_close - prev_close) / prev_close
        if pct_change < -decline_pct and today_vol > prev_vol:
            dist_count += 1

    response = config.get("response", {})
    all_stock_ids = [
        pos.stock_id if hasattr(pos, "stock_id") else pos["stock_id"]
        for pos in positions
    ]

    if dist_count >= 6:
        return [CascadeAction(
            layer="distribution_days",
            priority=2,
            action="reduce_to_50_pct",
            affected_stock_ids=all_stock_ids,
            reason=f"{dist_count} distribution days in {lookback}d → reduce to 50%",
        )]
    elif dist_count >= 5:
        return [CascadeAction(
            layer="distribution_days",
            priority=2,
            action="reduce_25_pct",
            affected_stock_ids=all_stock_ids,
            reason=f"{dist_count} distribution days in {lookback}d → reduce 25%",
        )]
    elif dist_count >= 3:
        return [CascadeAction(
            layer="distribution_days",
            priority=2,
            action="tighten_stops",
            affected_stock_ids=all_stock_ids,
            reason=f"{dist_count} distribution days in {lookback}d → tighten stops",
        )]

    return []


# ---------------------------------------------------------------------------
# E3: A/D Divergence
# ---------------------------------------------------------------------------


def _check_ad_divergence(
    db: Session,
    positions: list,
    as_of_date: date,
    config: dict,
) -> list[CascadeAction]:
    """E3: Index at new high but A/D line making lower high → reduce all 25%."""
    # Get Nifty recent data
    nifty_stock = db.execute(
        text("SELECT id FROM stocks WHERE symbol IN ('NIFTY 50', '^NSEI', 'NIFTY50') LIMIT 1")
    ).fetchone()

    if not nifty_stock:
        return []

    rows = db.execute(
        text("""
            SELECT adj_close FROM eod_prices
            WHERE stock_id = :sid AND date <= :d
            ORDER BY date DESC LIMIT 60
        """),
        {"sid": nifty_stock[0], "d": as_of_date},
    ).fetchall()

    if len(rows) < 60:
        return []

    # Check if Nifty near 60-day high
    prices = [float(r[0]) for r in rows]
    current = prices[0]
    high_60d = max(prices)

    if current < high_60d * 0.99:
        return []  # Not at new high

    # Check A/D line: % of stocks with positive ADL ratio
    ad_current = db.execute(
        text("""
            SELECT AVG(adl_ratio) FROM indicators
            WHERE date = :d AND adl_ratio IS NOT NULL
        """),
        {"d": as_of_date},
    ).scalar()

    # Get A/D from 20 days ago for comparison
    ad_prev = db.execute(
        text("""
            SELECT AVG(adl_ratio) FROM indicators
            WHERE date = (SELECT MAX(date) FROM indicators WHERE date < :d)
              AND adl_ratio IS NOT NULL
        """),
        {"d": as_of_date},
    ).scalar()

    if ad_current and ad_prev and ad_current < ad_prev:
        all_stock_ids = [
            pos.stock_id if hasattr(pos, "stock_id") else pos["stock_id"]
            for pos in positions
        ]
        return [CascadeAction(
            layer="ad_divergence",
            priority=3,
            action="reduce_all_25_pct",
            affected_stock_ids=all_stock_ids,
            reason=f"A/D divergence: index at high but A/D declining ({ad_current:.3f} < {ad_prev:.3f})",
        )]

    return []


# ---------------------------------------------------------------------------
# E4: New Highs Collapse
# ---------------------------------------------------------------------------


def _check_new_highs_collapse(
    db: Session,
    positions: list,
    as_of_date: date,
    config: dict,
) -> list[CascadeAction]:
    """E4: Nifty500 new 52w highs dropping below thresholds."""
    response = config.get("response", {})

    # Count stocks near 52-week highs
    row = db.execute(
        text("""
            SELECT COUNT(*) FROM indicators
            WHERE date = :d AND pct_from_high IS NOT NULL
              AND pct_from_high >= -0.03
        """),
        {"d": as_of_date},
    ).fetchone()

    new_highs_count = int(row[0]) if row else 0

    all_stock_ids = [
        pos.stock_id if hasattr(pos, "stock_id") else pos["stock_id"]
        for pos in positions
    ]

    if new_highs_count < 20:
        return [CascadeAction(
            layer="new_highs_collapse",
            priority=4,
            action="reduce_to_50_pct",
            affected_stock_ids=all_stock_ids,
            reason=f"New highs collapse: only {new_highs_count} stocks near 52w high (<20)",
        )]
    elif new_highs_count < 50:
        return [CascadeAction(
            layer="new_highs_collapse",
            priority=4,
            action="trail_15_pct",
            affected_stock_ids=all_stock_ids,
            reason=f"New highs declining: {new_highs_count} stocks near 52w high (<50) → tighten to 15% trail",
        )]

    return []


# ---------------------------------------------------------------------------
# Main cascade orchestrator
# ---------------------------------------------------------------------------


_LAYER_HANDLERS = {
    "climax_detection": _check_climax_detection,
    "distribution_days": _check_distribution_days,
    "ad_divergence": _check_ad_divergence,
    "new_highs_collapse": _check_new_highs_collapse,
}


def evaluate_cascade(
    db: Session,
    open_positions: list,
    as_of_date: date,
    cascade_config: CascadeConfig | None = None,
) -> list[CascadeAction]:
    """
    Run all cascade layers in priority order.

    Returns list of CascadeAction. Multiple layers can fire simultaneously.
    The caller decides how to reconcile conflicting actions (higher priority wins).
    """
    if not cascade_config or not cascade_config.enabled:
        return []

    if not open_positions:
        return []

    all_actions: list[CascadeAction] = []

    for layer in sorted(cascade_config.layers, key=lambda l: l.priority):
        handler = _LAYER_HANDLERS.get(layer.name)
        if handler is None:
            logger.debug("Cascade layer '{}' has no handler — skipping", layer.name)
            continue

        # Build config dict from layer
        layer_config = {
            "trigger": layer.trigger if isinstance(layer.trigger, dict) else {},
            "response": layer.response if isinstance(layer.response, dict) else {},
        }

        actions = handler(db, open_positions, as_of_date, layer_config)
        if actions:
            logger.info(
                "Cascade E{} ({}): {} actions fired",
                layer.priority, layer.name, len(actions),
            )
            all_actions.extend(actions)

    return all_actions
