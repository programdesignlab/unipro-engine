"""
v16 Exit Engine — 4-phase gain-based framework.

Phases (determined by unrealised gain %):
  prove_it         [0%, 25%)    — 8% fixed stop, regime exit only
  let_it_run       [25%, 100%)  — 20% trail, RS decay, MA weakness, climax
  working_compounder [100%, 200%) — 15% trail, tighter rules
  monster_run      [200%+]      — 50MA primary, partial exits, 12% trail on core

Monster override: score >= 80 AND gain >= 40% → force monster_run phase
  regardless of actual gain.

Each phase has rules evaluated in priority order (first match wins).
Three validation layers can suppress or override exit signals:
  1. Trend integrity: higher highs/lows intact → suppress 21DMA warning
  2. Volume direction: low vol on down days = hold; high vol = instant 25% exit
  3. ATR compression: suppress time stop if ATR compressed

All thresholds read from strategy.exits config.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.core.strategy import ExitConfig, StrategyConfig


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class GainPhase(str, Enum):
    PROVE_IT = "prove_it"
    LET_IT_RUN = "let_it_run"
    WORKING_COMPOUNDER = "working_compounder"
    MONSTER_RUN = "monster_run"


@dataclass
class ExitSignal:
    stock_id: int
    symbol: str
    exit_type: str       # stop / trailing / regime / rs_decay / ma_weakness / climax / time / partial
    action: str          # full_exit / partial_exit_25 / partial_exit_50 / move_stop / exit_20pct
    exit_pct: float      # fraction to exit (1.0 = full, 0.25, 0.50)
    new_stop: float | None
    phase: str           # which gain phase triggered this
    rule_name: str
    reason: str


# ---------------------------------------------------------------------------
# Phase determination
# ---------------------------------------------------------------------------


def determine_phase(gain_pct: float, monster_override: bool = False) -> GainPhase:
    """Map unrealised gain % to exit phase. Monster override forces monster_run."""
    if monster_override:
        return GainPhase.MONSTER_RUN
    if gain_pct >= 2.0:
        return GainPhase.MONSTER_RUN
    if gain_pct >= 1.0:
        return GainPhase.WORKING_COMPOUNDER
    if gain_pct >= 0.25:
        return GainPhase.LET_IT_RUN
    return GainPhase.PROVE_IT


# ---------------------------------------------------------------------------
# Market data helper
# ---------------------------------------------------------------------------


def _fetch_market_data(db: Session, stock_id: int, as_of_date: date) -> dict | None:
    """Fetch today's price bar, indicators, and 10-day/50-day highs."""
    row = db.execute(
        text("""
            SELECT e.adj_close, e.low, e.high, e.volume, e.open,
                   i.ma200, i.ma50, i.rs_rank, i.atr, i.adl_ratio
            FROM eod_prices e
            JOIN indicators i ON i.stock_id = e.stock_id AND i.date = e.date
            WHERE e.stock_id = :stock_id AND e.date = :as_of_date
        """),
        {"stock_id": stock_id, "as_of_date": as_of_date},
    ).fetchone()

    if row is None:
        return None

    # 10-day high (10 trading days)
    high_10d_row = db.execute(
        text("""
            SELECT MAX(high) FROM (
                SELECT high FROM eod_prices
                WHERE stock_id = :stock_id AND date <= :as_of_date
                ORDER BY date DESC LIMIT 10
            ) sub
        """),
        {"stock_id": stock_id, "as_of_date": as_of_date},
    ).fetchone()

    # 50-day high (for 10-week MA proxy)
    high_50d_row = db.execute(
        text("""
            SELECT MAX(high) FROM (
                SELECT high FROM eod_prices
                WHERE stock_id = :stock_id AND date <= :as_of_date
                ORDER BY date DESC LIMIT 50
            ) sub
        """),
        {"stock_id": stock_id, "as_of_date": as_of_date},
    ).fetchone()

    # Recent volume for down-day check
    recent_vol = db.execute(
        text("""
            SELECT volume, adj_close FROM eod_prices
            WHERE stock_id = :stock_id AND date <= :as_of_date
            ORDER BY date DESC LIMIT 20
        """),
        {"stock_id": stock_id, "as_of_date": as_of_date},
    ).fetchall()

    # Total ranked stocks (for RS percentile)
    total_row = db.execute(
        text("SELECT COUNT(*) FROM indicators WHERE date = :d AND rs_rank IS NOT NULL"),
        {"d": as_of_date},
    ).fetchone()

    # Average volume 20d
    avg_vol_20 = sum(r[0] for r in recent_vol) / len(recent_vol) if recent_vol else 0

    # Check if today is a down day
    is_down_day = False
    vol_ratio_today = None
    if len(recent_vol) >= 2:
        today_close = recent_vol[0][1]
        prev_close = recent_vol[1][1]
        is_down_day = today_close < prev_close
        vol_ratio_today = recent_vol[0][0] / avg_vol_20 if avg_vol_20 > 0 else 1.0

    return {
        "adj_close": float(row[0]),
        "low": float(row[1]),
        "high": float(row[2]),
        "volume": int(row[3]),
        "open": float(row[4]),
        "ma200": float(row[5]) if row[5] else None,
        "ma50": float(row[6]) if row[6] else None,
        "rs_rank": int(row[7]) if row[7] else None,
        "atr": float(row[8]) if row[8] else None,
        "adl_ratio": float(row[9]) if row[9] else None,
        "high_10d": float(high_10d_row[0]) if high_10d_row and high_10d_row[0] else None,
        "high_50d": float(high_50d_row[0]) if high_50d_row and high_50d_row[0] else None,
        "total_ranked": int(total_row[0]) if total_row else 0,
        "avg_vol_20": avg_vol_20,
        "is_down_day": is_down_day,
        "vol_ratio_today": vol_ratio_today,
    }


# ---------------------------------------------------------------------------
# Phase-specific exit rules
# ---------------------------------------------------------------------------


def _check_fixed_stop(position, mkt: dict, rule: dict) -> ExitSignal | None:
    """Phase 1 fixed stop: low < entry * (1 - stop_pct)."""
    stop_pct = rule.get("stop_pct", 0.08)
    stop_level = position.entry_price * (1 - stop_pct)

    if position.current_stop is not None:
        stop_level = max(stop_level, position.current_stop)

    if mkt["low"] < stop_level:
        return ExitSignal(
            stock_id=position.stock_id, symbol=position.symbol,
            exit_type="stop", action="full_exit", exit_pct=1.0,
            new_stop=None, phase=position.gain_phase or "prove_it",
            rule_name="fixed_stop",
            reason=f"Stop hit: low {mkt['low']:.2f} < stop {stop_level:.2f} ({stop_pct*100:.0f}% from entry)",
        )
    # Raise stop if not set
    if position.current_stop is None or position.current_stop < stop_level:
        return ExitSignal(
            stock_id=position.stock_id, symbol=position.symbol,
            exit_type="stop", action="move_stop", exit_pct=0.0,
            new_stop=stop_level, phase=position.gain_phase or "prove_it",
            rule_name="fixed_stop",
            reason=f"Set initial stop at {stop_level:.2f}",
        )
    return None


def _check_trailing_stop(position, mkt: dict, rule: dict) -> ExitSignal | None:
    """Trailing stop from 10-day (or 50-day) high."""
    trail_pct = rule.get("trail_pct", 0.20)
    ref = rule.get("reference", "10_week_high")

    if ref == "10_week_high":
        high_ref = mkt.get("high_50d") or mkt.get("high_10d")
    else:
        high_ref = mkt.get("high_10d")

    if high_ref is None:
        return None

    new_stop = round(high_ref * (1 - trail_pct), 2)

    # Only raise stop, never lower
    if position.current_stop is not None and new_stop <= position.current_stop:
        # Check if current price breached existing stop
        if mkt["low"] < position.current_stop:
            return ExitSignal(
                stock_id=position.stock_id, symbol=position.symbol,
                exit_type="trailing", action="full_exit", exit_pct=1.0,
                new_stop=None, phase=position.gain_phase or "",
                rule_name="trailing_stop",
                reason=f"Trailing stop hit: low {mkt['low']:.2f} < stop {position.current_stop:.2f}",
            )
        return None

    # Update trailing stop
    return ExitSignal(
        stock_id=position.stock_id, symbol=position.symbol,
        exit_type="trailing", action="move_stop", exit_pct=0.0,
        new_stop=new_stop, phase=position.gain_phase or "",
        rule_name="trailing_stop",
        reason=f"Trail {trail_pct*100:.0f}% from {ref} {high_ref:.2f} → stop {new_stop:.2f}",
    )


def _check_rs_decay(position, mkt: dict, rule: dict) -> ExitSignal | None:
    """RS rank below floor for N consecutive weeks → exit."""
    floor_pct = rule.get("floor_pct", 30)
    persist_weeks = rule.get("persist_weeks", 4)

    rs_rank = mkt.get("rs_rank")
    total = mkt.get("total_ranked", 0)
    if rs_rank is None or total == 0:
        return None

    # Calculate percentile (rank 1 = best → percentile near 100)
    percentile = ((total - rs_rank) / total) * 100
    below_floor = percentile < floor_pct

    if below_floor and position.rs_below_floor_weeks >= persist_weeks:
        return ExitSignal(
            stock_id=position.stock_id, symbol=position.symbol,
            exit_type="rs_decay", action="full_exit", exit_pct=1.0,
            new_stop=None, phase=position.gain_phase or "",
            rule_name="rs_decay",
            reason=f"RS percentile {percentile:.0f}% < {floor_pct}% for {position.rs_below_floor_weeks} weeks",
        )
    return None


def _check_ma_weakness(position, mkt: dict, rule: dict, as_of_date: date) -> ExitSignal | None:
    """Close below 21DMA for N confirm days (MA50 used as proxy for 21DMA)."""
    adj_close = mkt["adj_close"]
    ma50 = mkt.get("ma50")  # Using MA50 as intermediate trend proxy

    if ma50 is None:
        return None

    # Simple check: close below MA50
    if adj_close < ma50:
        volume_check = rule.get("volume_check", True)
        if volume_check and mkt.get("vol_ratio_today") and mkt["vol_ratio_today"] > 1.5:
            return ExitSignal(
                stock_id=position.stock_id, symbol=position.symbol,
                exit_type="ma_weakness", action="full_exit", exit_pct=1.0,
                new_stop=None, phase=position.gain_phase or "",
                rule_name="ma_weakness",
                reason=f"Close {adj_close:.2f} < MA50 {ma50:.2f} on heavy volume",
            )
    return None


def _check_climax_run(position, mkt: dict, rule: dict, as_of_date: date) -> ExitSignal | None:
    """Large gain in short time window → partial exit."""
    gain_threshold = rule.get("gain_threshold", 0.20)
    time_window = rule.get("time_window_days", 15)
    sell_pct = rule.get("sell_pct", 0.50)

    gain_pct = (mkt["adj_close"] - position.entry_price) / position.entry_price
    holding = (as_of_date - position.entry_date).days

    if gain_pct >= gain_threshold and holding <= time_window:
        return ExitSignal(
            stock_id=position.stock_id, symbol=position.symbol,
            exit_type="climax", action=f"partial_exit_{int(sell_pct*100)}",
            exit_pct=sell_pct, new_stop=None, phase=position.gain_phase or "",
            rule_name="climax_run",
            reason=f"Climax: {gain_pct*100:.1f}% gain in {holding} days (>{gain_threshold*100:.0f}% in <{time_window}d)",
        )
    return None


def _check_regime_exit(position, regime: str, crash_warning: bool, rule: dict) -> ExitSignal | None:
    """Bear or crash → gradual exit."""
    trigger = rule.get("trigger", "bear_or_crash")
    days = rule.get("days", 5)

    should_trigger = False
    trigger_reason = ""

    if trigger == "bear_or_crash":
        if crash_warning:
            should_trigger = True
            trigger_reason = "crash warning"
        elif regime in ("Bear", "Full Bear"):
            should_trigger = True
            trigger_reason = f"{regime} regime"

    if should_trigger:
        daily_pct = 1.0 / days
        return ExitSignal(
            stock_id=position.stock_id, symbol=position.symbol,
            exit_type="regime", action=f"exit_{int(daily_pct*100)}pct",
            exit_pct=daily_pct, new_stop=None, phase=position.gain_phase or "",
            rule_name="regime_exit",
            reason=f"Regime exit: {trigger_reason} → sell {daily_pct*100:.0f}%/day over {days} days",
        )
    return None


def _check_ma_breach(position, mkt: dict, rule: dict) -> ExitSignal | None:
    """Monster phase: close below MA50 (10-week proxy) = primary exit."""
    ma_period = rule.get("ma_period", 50)
    ma_value = mkt.get("ma50") if ma_period == 50 else mkt.get("ma200")

    if ma_value is None:
        return None

    if mkt["adj_close"] < ma_value:
        return ExitSignal(
            stock_id=position.stock_id, symbol=position.symbol,
            exit_type="ma_breach", action="full_exit", exit_pct=1.0,
            new_stop=None, phase="monster_run",
            rule_name="ma_breach",
            reason=f"Monster primary exit: close {mkt['adj_close']:.2f} < MA{ma_period} {ma_value:.2f}",
        )
    return None


def _check_partial_exit(position, mkt: dict, rule: dict) -> ExitSignal | None:
    """Monster phase: partial exit at new highs."""
    max_partials = rule.get("max_partials", 2)
    sell_pct = rule.get("sell_pct", 0.25)

    if position.partial_exits_taken >= max_partials:
        return None

    # Check if we're at a new high
    if mkt.get("high_10d") and mkt["adj_close"] >= mkt["high_10d"] * 0.99:
        return ExitSignal(
            stock_id=position.stock_id, symbol=position.symbol,
            exit_type="partial", action=f"partial_exit_{int(sell_pct*100)}",
            exit_pct=sell_pct, new_stop=None, phase="monster_run",
            rule_name="partial_exit_at_highs",
            reason=f"Monster partial #{position.partial_exits_taken + 1}: sell {sell_pct*100:.0f}% at new high",
        )
    return None


# ---------------------------------------------------------------------------
# Validation layers
# ---------------------------------------------------------------------------


def _apply_trend_integrity(signal: ExitSignal | None, position, mkt: dict, config: dict) -> ExitSignal | None:
    """Suppress MA weakness exit if trend structure (higher highs/lows) is intact."""
    if signal is None or signal.rule_name != "ma_weakness":
        return signal

    # Check recent price structure for higher highs/higher lows
    # Simple heuristic: if current price > entry and recent high > prior high
    if mkt["adj_close"] > position.entry_price and mkt.get("high_10d"):
        if mkt["high"] >= mkt["high_10d"] * 0.98:  # near recent highs
            logger.debug(
                "{}: trend integrity override — suppressing MA weakness exit",
                position.symbol,
            )
            return None
    return signal


def _apply_volume_direction(signal: ExitSignal | None, position, mkt: dict, config: dict) -> ExitSignal | None:
    """
    Volume on down days:
    - vol < hold_threshold on down days → suppress exit (hold)
    - vol > distribution_threshold on down days → instant partial exit
    """
    params = config.get("params", {})
    hold_thresh = params.get("hold_threshold", 0.75)
    dist_thresh = params.get("distribution_threshold", 1.50)
    dist_exit_pct = params.get("distribution_exit_pct", 0.25)

    if not mkt.get("is_down_day"):
        return signal

    vol_ratio = mkt.get("vol_ratio_today")
    if vol_ratio is None:
        return signal

    # Heavy distribution on down day → instant partial exit (overrides everything)
    if vol_ratio > dist_thresh:
        return ExitSignal(
            stock_id=position.stock_id, symbol=position.symbol,
            exit_type="distribution", action=f"partial_exit_{int(dist_exit_pct*100)}",
            exit_pct=dist_exit_pct, new_stop=None,
            phase=position.gain_phase or "",
            rule_name="volume_distribution",
            reason=f"Distribution day: vol {vol_ratio:.2f}x avg on down day → sell {dist_exit_pct*100:.0f}%",
        )

    # Low volume on down day → suppress non-critical exits (hold signal)
    if vol_ratio < hold_thresh and signal is not None:
        if signal.rule_name in ("ma_weakness", "rs_decay"):
            logger.debug(
                "{}: low vol ({:.2f}x) on down day — suppressing {} exit",
                position.symbol, vol_ratio, signal.rule_name,
            )
            return None

    return signal


def _apply_atr_compression(signal: ExitSignal | None, position, mkt: dict, config: dict) -> ExitSignal | None:
    """Suppress time-based exits if ATR is compressed (stock consolidating)."""
    if signal is None or signal.rule_name not in ("time_stop",):
        return signal

    params = config.get("params", {})
    compression_ratio = params.get("compression_ratio", 0.70)

    current_atr = mkt.get("atr")
    entry_atr = position.entry_atr

    if current_atr and entry_atr and entry_atr > 0:
        if current_atr < entry_atr * compression_ratio:
            logger.debug(
                "{}: ATR compressed ({:.2f} < {:.2f} * {:.0f}%) — suppressing time stop",
                position.symbol, current_atr, entry_atr, compression_ratio * 100,
            )
            return None
    return signal


# ---------------------------------------------------------------------------
# Rule dispatcher
# ---------------------------------------------------------------------------


_RULE_HANDLERS = {
    "fixed_stop": lambda pos, mkt, rule, **kw: _check_fixed_stop(pos, mkt, rule),
    "trailing_stop": lambda pos, mkt, rule, **kw: _check_trailing_stop(pos, mkt, rule),
    "rs_decay": lambda pos, mkt, rule, **kw: _check_rs_decay(pos, mkt, rule),
    "ma_weakness": lambda pos, mkt, rule, **kw: _check_ma_weakness(pos, mkt, rule, kw.get("as_of_date")),
    "climax_run": lambda pos, mkt, rule, **kw: _check_climax_run(pos, mkt, rule, kw.get("as_of_date")),
    "regime_exit": lambda pos, mkt, rule, **kw: _check_regime_exit(pos, kw.get("regime", ""), kw.get("crash_warning", False), rule),
    "ma_breach": lambda pos, mkt, rule, **kw: _check_ma_breach(pos, mkt, rule),
    "partial_exit": lambda pos, mkt, rule, **kw: _check_partial_exit(pos, mkt, rule),
}


def _evaluate_phase_rules(
    position,
    mkt: dict,
    phase_rules: list[dict],
    as_of_date: date,
    regime: str,
    crash_warning: bool,
) -> ExitSignal | None:
    """Evaluate rules for a phase in priority order. First match wins."""
    for rule in phase_rules:
        rule_type = rule.get("type", "")
        handler = _RULE_HANDLERS.get(rule_type)
        if handler is None:
            logger.warning("Unknown exit rule type: {}", rule_type)
            continue

        # Convert ExitRuleConfig to dict if needed
        rule_dict = rule if isinstance(rule, dict) else rule.model_dump()

        signal = handler(
            position, mkt, rule_dict,
            as_of_date=as_of_date,
            regime=regime,
            crash_warning=crash_warning,
        )

        if signal is not None and signal.action != "move_stop":
            return signal
        elif signal is not None and signal.action == "move_stop":
            # Stop moves are collected but don't stop evaluation
            # Return the move_stop so caller can update position
            return signal

    return None


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def check_exits(
    db: Session,
    open_positions: list,
    as_of_date: date,
    regime: str,
    crash_warning: bool,
    strategy: StrategyConfig | None = None,
) -> list[ExitSignal]:
    """
    Check v16 4-phase exit rules for each open position.

    Positions can be OpenPosition ORM instances or dicts with compatible keys.
    Returns list of ExitSignal actions to take.
    """
    signals: list[ExitSignal] = []

    # Get exit config from strategy
    exit_config = strategy.exits if strategy else None

    # Build validation layer lookup
    validation_layers = {}
    if exit_config:
        for layer in exit_config.validation_layers:
            if layer.enabled:
                validation_layers[layer.name] = {
                    "params": layer.params,
                    "description": layer.description,
                }

    for pos in open_positions:
        # Support both ORM objects and dicts
        stock_id = pos.stock_id if hasattr(pos, "stock_id") else pos["stock_id"]
        symbol = pos.symbol if hasattr(pos, "symbol") else pos["symbol"]

        mkt = _fetch_market_data(db, stock_id, as_of_date)
        if mkt is None:
            logger.warning("No market data for {} on {} — skipping exit checks", symbol, as_of_date)
            continue

        # Determine gain phase
        entry_price = pos.entry_price if hasattr(pos, "entry_price") else pos["entry_price"]
        gain_pct = (mkt["adj_close"] - entry_price) / entry_price
        monster_override = pos.monster_override_active if hasattr(pos, "monster_override_active") else pos.get("monster_override_active", False)

        phase = determine_phase(gain_pct, monster_override)

        # Get rules for this phase from strategy
        if exit_config:
            phase_config = exit_config.get_phase(phase.value)
            if phase_config:
                phase_rules = [r.model_dump() for r in phase_config.rules]
            else:
                phase_rules = []
        else:
            # Fallback: no strategy config
            phase_rules = []

        # Evaluate phase rules
        signal = _evaluate_phase_rules(
            pos, mkt, phase_rules, as_of_date, regime, crash_warning,
        )

        # Apply validation layers
        if "trend_integrity" in validation_layers:
            signal = _apply_trend_integrity(signal, pos, mkt, validation_layers["trend_integrity"])
        if "volume_direction" in validation_layers:
            signal = _apply_volume_direction(signal, pos, mkt, validation_layers["volume_direction"])
        if "atr_compression" in validation_layers:
            signal = _apply_atr_compression(signal, pos, mkt, validation_layers["atr_compression"])

        if signal is not None:
            logger.info(
                "Exit signal for {} [{}]: {} — {}",
                symbol, phase.value, signal.exit_type, signal.reason,
            )
            signals.append(signal)

    logger.info("Exit engine: {} signals from {} positions", len(signals), len(open_positions))
    return signals
