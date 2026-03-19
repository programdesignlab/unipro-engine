"""
M8 — Breakout Pattern Detection (v7).

Detects VCP (Volatility Contraction Pattern), tight base, and breakout patterns
for stocks that have passed the Trend Template.

VCP detection uses full contraction math:
  - Find base start from most recent pivot high in last 252 days
  - Extract contractions (high-to-low swings getting shallower)
  - Validate: 3+ contractions, each shallower, volume declining
  - Base validation: 5-52 weeks, overall depth <= 40%
  - Circuit breaker exclusion during base
  - OBV slope & divergence from base_start

Entry rules (7 conditions, all must pass for entry_valid):
  1. adj_close > pivot (breakout day)
  2. Volume >= 1.5x 50-day average
  3. Strong close: (close - low) / (high - low) >= 0.75
  4. Not too extended: close <= pivot * 1.05
  5. Not upper circuit day
  6. Earnings not within 10 days
  7. Next-day open <= pivot * 1.03 (post-hoc check)

Returns PatternResult with breakout score (max 10 pts) + OBV bonus (0 or 5).
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class PatternResult:
    pattern_type: str | None  # VCP, TightBase, Breakout, None
    signal_strength: str | None  # VeryHigh, High, Medium, None
    breakout_score: float  # 0-10
    stop_loss_level: float
    pivot_price: float | None
    entry_zone_low: float | None
    entry_zone_high: float | None
    obv_slope: float | None
    obv_bonus: int  # 0 or 5
    obv_divergence: bool
    base_length_days: int | None
    base_depth_pct: float | None
    volume_ratio: float | None
    entry_valid: bool
    entry_fail_reason: str | None


def _find_local_highs(highs: np.ndarray, order: int = 5) -> list[int]:
    """Return indices of local highs (pivot highs).

    A local high at index i means highs[i] >= all values in
    highs[i-order : i+order+1].
    """
    pivots: list[int] = []
    for i in range(order, len(highs) - order):
        window = highs[i - order : i + order + 1]
        if highs[i] == np.max(window):
            pivots.append(i)
    return pivots


def _find_local_lows(lows: np.ndarray, order: int = 5) -> list[int]:
    """Return indices of local lows."""
    pivots: list[int] = []
    for i in range(order, len(lows) - order):
        window = lows[i - order : i + order + 1]
        if lows[i] == np.min(window):
            pivots.append(i)
    return pivots


def _compute_obv(closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    """Compute On-Balance Volume series."""
    obv = np.zeros(len(closes))
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv[i] = obv[i - 1] + volumes[i]
        elif closes[i] < closes[i - 1]:
            obv[i] = obv[i - 1] - volumes[i]
        else:
            obv[i] = obv[i - 1]
    return obv


def _detect_vcp(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    hit_upper_circuit: np.ndarray,
) -> dict | None:
    """Detect VCP pattern. Returns dict with base info or None."""
    n = len(closes)
    if n < 60:
        return None

    # --- Step 1: Find base start (most recent pivot high in last 252 days) ---
    lookback = min(n, 252)
    segment_highs = highs[-lookback:]
    pivot_indices = _find_local_highs(segment_highs, order=5)
    if not pivot_indices:
        return None

    # Most recent dominant pivot high = highest local high
    best_pivot_idx = max(pivot_indices, key=lambda i: segment_highs[i])
    # Convert to absolute index
    base_start_abs = n - lookback + best_pivot_idx
    base_start_price = highs[base_start_abs]

    # Base must have at least 25 trading days (~ 5 weeks) after pivot
    days_in_base = n - 1 - base_start_abs
    if days_in_base < 25:
        return None
    # Max 260 trading days (~ 52 weeks)
    if days_in_base > 260:
        return None

    # --- Step 2: Circuit breaker exclusion ---
    base_circuit = hit_upper_circuit[base_start_abs:]
    if np.any(base_circuit):
        return None

    # --- Step 3: Overall base depth ---
    base_lows = lows[base_start_abs:]
    base_low = np.min(base_lows)
    base_depth_pct = (base_start_price - base_low) / base_start_price * 100
    if base_depth_pct > 40:
        return None

    # --- Step 4: Extract contractions ---
    # Split the base period into segments between local highs
    base_highs = highs[base_start_abs:]
    base_lows_seg = lows[base_start_abs:]
    seg_len = len(base_highs)

    local_high_indices = _find_local_highs(base_highs, order=3)
    if len(local_high_indices) < 2:
        # Not enough structure for contractions — try fixed segments
        # Fall back to splitting into equal segments
        num_segs = max(3, seg_len // 10)
        seg_size = seg_len // num_segs
        if seg_size < 5:
            return None
        contractions = []
        for i in range(num_segs):
            s = i * seg_size
            e = min(s + seg_size, seg_len)
            seg_high = np.max(base_highs[s:e])
            seg_low = np.min(base_lows_seg[s:e])
            depth = (seg_high - seg_low) / seg_high * 100 if seg_high > 0 else 0
            contractions.append(depth)
    else:
        # Use segments between consecutive local highs
        # Add end of data as final boundary
        boundaries = [0] + local_high_indices + [seg_len - 1]
        contractions = []
        for i in range(len(boundaries) - 1):
            s = boundaries[i]
            e = boundaries[i + 1] + 1
            if e - s < 3:
                continue
            seg_high = np.max(base_highs[s:e])
            seg_low = np.min(base_lows_seg[s:e])
            depth = (seg_high - seg_low) / seg_high * 100 if seg_high > 0 else 0
            contractions.append(depth)

    # Need 3+ contractions, each shallower than previous
    if len(contractions) < 3:
        return None

    is_contracting = all(
        contractions[i] >= contractions[i + 1] for i in range(len(contractions) - 1)
    )
    if not is_contracting:
        return None

    # --- Step 5: Volume declining during base ---
    base_volumes = volumes[base_start_abs:]
    half = len(base_volumes) // 2
    if half < 5:
        return None
    vol_first_half = np.mean(base_volumes[:half])
    vol_second_half = np.mean(base_volumes[half:])
    volume_declining = vol_second_half < vol_first_half

    if not volume_declining:
        return None

    # --- Step 6: OBV slope from base_start ---
    base_closes = closes[base_start_abs:]
    base_vols = volumes[base_start_abs:]
    obv = _compute_obv(base_closes, base_vols)
    x = np.arange(len(obv), dtype=float)
    obv_coeffs = np.polyfit(x, obv, 1)
    obv_slope = float(obv_coeffs[0])
    obv_bonus = 5 if obv_slope > 0 else 0

    # OBV divergence: price makes lower low but OBV makes higher low
    obv_divergence = False
    price_local_lows = _find_local_lows(base_closes, order=3)
    obv_local_lows = _find_local_lows(obv, order=3)
    if len(price_local_lows) >= 2 and len(obv_local_lows) >= 2:
        # Compare last two lows
        p_low1 = base_closes[price_local_lows[-2]]
        p_low2 = base_closes[price_local_lows[-1]]
        o_low1 = obv[obv_local_lows[-2]]
        o_low2 = obv[obv_local_lows[-1]]
        if p_low2 < p_low1 and o_low2 > o_low1:
            obv_divergence = True

    # --- Step 7: Pivot = last contraction high ---
    # The pivot is the high of the last contraction
    last_seg_start = local_high_indices[-1] if local_high_indices else seg_len - 10
    last_seg_start = max(0, last_seg_start)
    pivot_price = float(np.max(base_highs[last_seg_start:]))

    # --- Step 8: Scoring ---
    contraction_ratio = contractions[-1] / contractions[0] if contractions[0] > 0 else 1
    if contraction_ratio < 0.3 and len(contractions) >= 4:
        score = 10.0
        strength = "VeryHigh"
    elif contraction_ratio < 0.5 and len(contractions) >= 3:
        score = 8.0
        strength = "High"
    else:
        score = 6.0
        strength = "Medium"

    # Boost for OBV divergence
    if obv_divergence:
        score = min(10.0, score + 1.0)

    return {
        "base_start_abs": base_start_abs,
        "base_length_days": days_in_base,
        "base_depth_pct": round(base_depth_pct, 2),
        "pivot_price": round(pivot_price, 2),
        "entry_zone_low": round(pivot_price, 2),
        "entry_zone_high": round(pivot_price * 1.05, 2),
        "stop_loss": round(float(base_low), 2),
        "obv_slope": round(obv_slope, 4),
        "obv_bonus": obv_bonus,
        "obv_divergence": obv_divergence,
        "score": round(score, 1),
        "strength": strength,
        "num_contractions": len(contractions),
    }


def _detect_tight_base(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
) -> dict | None:
    """Detect tight consolidation base: price range <10% over 25+ days,
    with declining volume."""
    if len(closes) < 25:
        return None

    base_range = (np.max(highs[-25:]) - np.min(lows[-25:])) / np.mean(closes[-25:]) * 100
    vol_declining = np.mean(volumes[-10:]) < np.mean(volumes[-25:-10]) * 0.85

    if base_range >= 10 or not vol_declining:
        return None

    pivot_price = float(np.max(highs[-25:]))
    stop_loss = float(np.min(lows[-25:]))

    return {
        "pivot_price": round(pivot_price, 2),
        "entry_zone_low": round(pivot_price, 2),
        "entry_zone_high": round(pivot_price * 1.05, 2),
        "stop_loss": round(stop_loss, 2),
        "base_length_days": 25,
        "base_depth_pct": round(base_range, 2),
        "score": 7.0,
        "strength": "High",
    }


def _detect_breakout(
    highs: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    current_close: float,
    current_volume: float,
    avg_volume_50: float,
) -> dict | None:
    """Detect resistance breakout on volume."""
    if len(closes) < 20:
        return None

    pivot_range_highs = highs[-20:-5]
    pivot_high = float(np.max(pivot_range_highs))
    volume_surge = current_volume > avg_volume_50 * 1.5

    if current_close <= pivot_high or not volume_surge:
        return None

    return {
        "pivot_price": round(pivot_high, 2),
        "entry_zone_low": round(pivot_high, 2),
        "entry_zone_high": round(pivot_high * 1.05, 2),
        "stop_loss": round(pivot_high * 0.97, 2),
        "score": 6.0,
        "strength": "Medium",
    }


def _check_entry_rules(
    db: Session,
    stock_id: int,
    target_date: date,
    current_close: float,
    current_high: float,
    current_low: float,
    current_volume: float,
    avg_volume_50: float,
    hit_uc_today: bool,
    pivot_price: float,
) -> tuple[bool, str | None]:
    """Check all 7 entry rules. Returns (entry_valid, fail_reason)."""

    # Rule 1: adj_close > pivot
    if current_close <= pivot_price:
        return False, "close_below_pivot"

    # Rule 2: volume >= 1.5x 50-day average
    if current_volume < avg_volume_50 * 1.5:
        return False, "volume_insufficient"

    # Rule 3: strong close: (close - low) / (high - low) >= 0.75
    day_range = current_high - current_low
    if day_range > 0:
        close_strength = (current_close - current_low) / day_range
        if close_strength < 0.75:
            return False, "weak_close"
    else:
        return False, "zero_range_day"

    # Rule 4: not too extended: close <= pivot * 1.05
    if current_close > pivot_price * 1.05:
        return False, "too_extended"

    # Rule 5: not upper circuit day
    if hit_uc_today:
        return False, "upper_circuit_day"

    # Rule 6: earnings not within 10 days
    row = db.execute(
        text("""
            SELECT expected_result_date
            FROM fundamentals
            WHERE stock_id = :stock_id
              AND expected_result_date IS NOT NULL
            ORDER BY quarter DESC
            LIMIT 1
        """),
        {"stock_id": stock_id},
    ).fetchone()

    if row and row[0]:
        earnings_date = row[0]
        if isinstance(earnings_date, date):
            days_to_earnings = (earnings_date - target_date).days
            if 0 <= days_to_earnings <= 10:
                return False, "earnings_within_10_days"

    # Rule 7: next-day open <= pivot * 1.03
    # This is a post-hoc check — look for the next trading day after target_date
    next_day_row = db.execute(
        text("""
            SELECT open
            FROM eod_prices
            WHERE stock_id = :stock_id AND date > :target_date
            ORDER BY date ASC
            LIMIT 1
        """),
        {"stock_id": stock_id, "target_date": target_date},
    ).fetchone()

    if next_day_row and next_day_row[0]:
        next_open = float(next_day_row[0])
        if next_open > pivot_price * 1.03:
            return False, "next_day_open_too_high"

    return True, None


def detect_pattern(
    db: Session, stock_id: int, symbol: str, target_date: date
) -> PatternResult:
    """Detect breakout patterns for a single stock.

    Requires at least 60 days of price data. Pulls up to 252 days
    for full VCP base detection.
    """
    # Fetch up to 252 days of price data
    rows = db.execute(
        text("""
            SELECT date, open, high, low, adj_close, volume, hit_upper_circuit
            FROM eod_prices
            WHERE stock_id = :stock_id AND date <= :target_date
            ORDER BY date DESC
            LIMIT 252
        """),
        {"stock_id": stock_id, "target_date": target_date},
    ).fetchall()

    if len(rows) < 60:
        logger.debug(
            "M8 skip {}: only {} days of data (need 60)", symbol, len(rows)
        )
        return PatternResult(
            pattern_type=None,
            signal_strength=None,
            breakout_score=0.0,
            stop_loss_level=0.0,
            pivot_price=None,
            entry_zone_low=None,
            entry_zone_high=None,
            obv_slope=None,
            obv_bonus=0,
            obv_divergence=False,
            base_length_days=None,
            base_depth_pct=None,
            volume_ratio=None,
            entry_valid=False,
            entry_fail_reason="insufficient_data",
        )

    # Reverse to chronological order
    rows = list(reversed(rows))

    highs = np.array([float(r[2]) for r in rows], dtype=float)
    lows = np.array([float(r[3]) for r in rows], dtype=float)
    closes = np.array([float(r[4]) if r[4] is not None else float(r[3]) for r in rows], dtype=float)
    volumes = np.array([float(r[5]) for r in rows], dtype=float)
    hit_upper_circuit = np.array([bool(r[6]) for r in rows], dtype=bool)

    current_close = closes[-1]
    current_high = highs[-1]
    current_low = lows[-1]
    current_volume = volumes[-1]
    hit_uc_today = hit_upper_circuit[-1]
    avg_volume_50 = float(np.mean(volumes[-50:])) if len(volumes) >= 50 else float(np.mean(volumes))

    # Also fetch vol_ratio_50 from indicators if available
    ind_row = db.execute(
        text("""
            SELECT vol_ratio_50
            FROM indicators
            WHERE stock_id = :stock_id AND date = :target_date
            LIMIT 1
        """),
        {"stock_id": stock_id, "target_date": target_date},
    ).fetchone()

    vol_ratio_50 = float(ind_row[0]) if ind_row and ind_row[0] else None
    volume_ratio = vol_ratio_50 if vol_ratio_50 else (
        round(current_volume / avg_volume_50, 2) if avg_volume_50 > 0 else None
    )

    # --- Try VCP first (highest priority) ---
    vcp = _detect_vcp(highs, lows, closes, volumes, hit_upper_circuit)

    if vcp:
        pivot_price = vcp["pivot_price"]
        entry_valid, fail_reason = _check_entry_rules(
            db, stock_id, target_date,
            current_close, current_high, current_low,
            current_volume, avg_volume_50, hit_uc_today,
            pivot_price,
        )
        return PatternResult(
            pattern_type="VCP",
            signal_strength=vcp["strength"],
            breakout_score=vcp["score"],
            stop_loss_level=vcp["stop_loss"],
            pivot_price=pivot_price,
            entry_zone_low=vcp["entry_zone_low"],
            entry_zone_high=vcp["entry_zone_high"],
            obv_slope=vcp["obv_slope"],
            obv_bonus=vcp["obv_bonus"],
            obv_divergence=vcp["obv_divergence"],
            base_length_days=vcp["base_length_days"],
            base_depth_pct=vcp["base_depth_pct"],
            volume_ratio=volume_ratio,
            entry_valid=entry_valid,
            entry_fail_reason=fail_reason,
        )

    # --- Try tight base ---
    tight = _detect_tight_base(highs, lows, closes, volumes)

    if tight:
        pivot_price = tight["pivot_price"]

        # Compute OBV for last 25 days
        base_closes = closes[-25:]
        base_vols = volumes[-25:]
        obv = _compute_obv(base_closes, base_vols)
        x = np.arange(len(obv), dtype=float)
        obv_coeffs = np.polyfit(x, obv, 1)
        obv_slope = float(obv_coeffs[0])
        obv_bonus = 5 if obv_slope > 0 else 0

        entry_valid, fail_reason = _check_entry_rules(
            db, stock_id, target_date,
            current_close, current_high, current_low,
            current_volume, avg_volume_50, hit_uc_today,
            pivot_price,
        )
        return PatternResult(
            pattern_type="TightBase",
            signal_strength=tight["strength"],
            breakout_score=tight["score"],
            stop_loss_level=tight["stop_loss"],
            pivot_price=pivot_price,
            entry_zone_low=tight["entry_zone_low"],
            entry_zone_high=tight["entry_zone_high"],
            obv_slope=round(obv_slope, 4),
            obv_bonus=obv_bonus,
            obv_divergence=False,
            base_length_days=tight["base_length_days"],
            base_depth_pct=tight["base_depth_pct"],
            volume_ratio=volume_ratio,
            entry_valid=entry_valid,
            entry_fail_reason=fail_reason,
        )

    # --- Try resistance breakout ---
    brk = _detect_breakout(
        highs, closes, volumes, current_close, current_volume, avg_volume_50
    )

    if brk:
        pivot_price = brk["pivot_price"]
        entry_valid, fail_reason = _check_entry_rules(
            db, stock_id, target_date,
            current_close, current_high, current_low,
            current_volume, avg_volume_50, hit_uc_today,
            pivot_price,
        )
        return PatternResult(
            pattern_type="Breakout",
            signal_strength=brk["strength"],
            breakout_score=brk["score"],
            stop_loss_level=brk["stop_loss"],
            pivot_price=pivot_price,
            entry_zone_low=brk["entry_zone_low"],
            entry_zone_high=brk["entry_zone_high"],
            obv_slope=None,
            obv_bonus=0,
            obv_divergence=False,
            base_length_days=None,
            base_depth_pct=None,
            volume_ratio=volume_ratio,
            entry_valid=entry_valid,
            entry_fail_reason=fail_reason,
        )

    # --- No pattern detected ---
    return PatternResult(
        pattern_type=None,
        signal_strength=None,
        breakout_score=0.0,
        stop_loss_level=0.0,
        pivot_price=None,
        entry_zone_low=None,
        entry_zone_high=None,
        obv_slope=None,
        obv_bonus=0,
        obv_divergence=False,
        base_length_days=None,
        base_depth_pct=None,
        volume_ratio=volume_ratio,
        entry_valid=False,
        entry_fail_reason="no_pattern",
    )
