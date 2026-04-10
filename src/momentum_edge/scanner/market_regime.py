"""
M2 — Market Regime Detection (v7).

Classifies the broad market into one of five regimes using 6 signals,
a crash indicator (Dierkes & Krupski 2022), and a stability rule.

Signals (0-6 total):
  S1: Nifty close > 200-day MA                          (0 or 1)
  S2: 200-day MA slope rising (today vs 20 days ago)     (0 or 1)
  S3: Breadth — % stocks above 50-day MA                 (0, 0.5, or 1)
  S4: New 52-week highs vs lows ratio                    (0, 0.5, or 1)
  S5: Nifty extension from 200-day MA                    (0, 0.5, or 1)
  S6: Nifty 12-minus-1-month return positive             (0 or 1)

Crash indicator:
  2-year return < -20% AND 1-month return > +10% → force Full Bear.

Stability rule:
  Regime changes only after 3 consecutive days at the new level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


class RegimeEnum(str, Enum):
    STRONG_BULL = "Strong Bull"
    BULL = "Bull"
    WEAK = "Weak"
    BEAR = "Bear"
    FULL_BEAR = "Full Bear"


# Keep old name as alias for backwards compatibility
Regime = RegimeEnum


@dataclass
class RegimeResult:
    regime: RegimeEnum
    score: float  # 0-6
    signals: dict  # s1-s6 values
    crash_warning: bool
    max_equity_pct: float
    max_positions: int
    risk_per_trade_pct: float
    exposure: str  # descriptive

    # Legacy compat properties
    @property
    def nifty_above_200ma(self) -> bool:
        return bool(self.signals.get("s1", 0))

    @property
    def pct_above_50ma(self) -> float:
        return self.signals.get("s3_pct", 50.0)

    @property
    def highs_gt_lows(self) -> bool:
        return self.signals.get("s4", 0) > 0

    @property
    def signals_positive(self) -> int:
        return sum(1 for k in ("s1", "s2", "s3", "s4", "s5", "s6") if self.signals.get(k, 0) >= 1)


# ── Regime allocation table ──────────────────────────────────────────────────

_REGIME_TABLE: list[tuple[float, float, RegimeEnum, float, int, float, str]] = [
    # min_score, max_score, regime, equity%, positions, risk%, exposure label
    (5.0, 6.0, RegimeEnum.STRONG_BULL, 100.0, 15, 2.0, "Aggressive"),
    (4.0, 5.0, RegimeEnum.BULL, 80.0, 12, 1.5, "Growth"),
    (2.5, 4.0, RegimeEnum.WEAK, 50.0, 8, 1.0, "Moderate"),
    (1.0, 2.5, RegimeEnum.BEAR, 25.0, 4, 0.5, "Defensive"),
    (0.0, 1.0, RegimeEnum.FULL_BEAR, 0.0, 0, 0.0, "Exit All"),
]


def _score_to_regime(
    score: float, crash_warning: bool
) -> tuple[RegimeEnum, float, int, float, str]:
    """Map composite score (and crash flag) to regime + allocation params."""
    if crash_warning:
        return RegimeEnum.FULL_BEAR, 0.0, 0, 0.0, "Exit All (Crash)"

    for min_s, max_s, regime, equity, positions, risk, exposure in _REGIME_TABLE:
        if min_s <= score <= max_s:
            return regime, equity, positions, risk, exposure

    # Fallback — should not happen with valid 0-6 score
    return RegimeEnum.FULL_BEAR, 0.0, 0, 0.0, "Exit All"


# ── Signal computation ────────────────────────────────────────────────────────


def _compute_nifty_signals(
    nifty_df, target_date: date
) -> tuple[float, float, float, float, bool]:
    """
    Compute S1, S2, S5, S6, and crash indicator from Nifty index data.

    Returns (s1, s2, s5, s6, crash_warning).
    """
    import pandas as pd

    nifty = nifty_df[nifty_df["date"] <= target_date].sort_values("date")

    if len(nifty) < 504:
        logger.warning(
            "[M2] Need 504 trading days of Nifty history; have {}",
            len(nifty),
        )

    nifty_close = nifty["close"].iloc[-1]

    # ── S1: Nifty close > 200-day MA ──
    if len(nifty) >= 200:
        ma200_today = nifty["close"].tail(200).mean()
        s1 = 1.0 if nifty_close > ma200_today else 0.0
    else:
        ma200_today = nifty_close
        s1 = 0.0

    # ── S2: 200-day MA slope (today vs 20 days ago) ──
    if len(nifty) >= 220:
        ma200_20d_ago = nifty["close"].iloc[-220:-20].tail(200).mean()
        s2 = 1.0 if ma200_today > ma200_20d_ago else 0.0
    else:
        s2 = 0.0

    # ── S5: Nifty extension from 200-day MA ──
    if len(nifty) >= 200:
        extension_pct = ((nifty_close - ma200_today) / ma200_today) * 100
        # Use absolute value — both over-extension and deep discount are risky
        abs_ext = abs(extension_pct)
        if abs_ext <= 15:
            s5 = 1.0
        elif abs_ext <= 25:
            s5 = 0.5
        else:
            s5 = 0.0
    else:
        s5 = 0.5

    # ── S6: 12-minus-1 month return positive ──
    # Approximately 252 trading days = 12 months, 21 = 1 month
    if len(nifty) >= 252:
        close_12m_ago = nifty["close"].iloc[-252]
        close_1m_ago = nifty["close"].iloc[-21] if len(nifty) >= 21 else nifty_close
        return_12_minus_1 = (close_1m_ago / close_12m_ago) - 1
        s6 = 1.0 if return_12_minus_1 > 0 else 0.0
    else:
        s6 = 0.0

    # ── Crash indicator (Dierkes & Krupski 2022) ──
    crash_warning = False
    if len(nifty) >= 504:
        nifty_2yr_return = (nifty_close / nifty["close"].iloc[-504]) - 1
        nifty_1m_return = (nifty_close / nifty["close"].iloc[-21]) - 1
        crash_warning = (nifty_2yr_return < -0.20) and (nifty_1m_return > 0.10)

    return s1, s2, s5, s6, crash_warning


def _compute_breadth(db: Session, target_date: date) -> tuple[float, float]:
    """
    S3: % of active stocks with close > 50-day MA.

    Returns (s3_score, raw_pct).
    """
    row = db.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE i.ma50 IS NOT NULL AND e.close > i.ma50
                ) AS above_50ma
            FROM indicators i
            JOIN stocks s ON s.id = i.stock_id
            JOIN eod_prices e ON e.stock_id = i.stock_id AND e.date = i.date
            WHERE i.date = :target_date AND s.is_active = true
        """),
        {"target_date": target_date},
    ).fetchone()

    total = row[0] if row else 0
    above_50ma = row[1] if row else 0
    pct = (above_50ma / total * 100) if total > 0 else 50.0

    if pct > 60:
        s3 = 1.0
    elif pct >= 40:
        s3 = 0.5
    else:
        s3 = 0.0

    return s3, round(pct, 1)


def _compute_highs_lows(db: Session, target_date: date) -> tuple[float, int, int]:
    """
    S4: New 52-week highs vs lows ratio.

    Returns (s4_score, near_highs_count, near_lows_count).
    """
    hl_row = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (
                    WHERE e.close >= i.high_52w * 0.97
                ) AS near_highs,
                COUNT(*) FILTER (
                    WHERE e.close <= i.low_52w * 1.03
                ) AS near_lows
            FROM indicators i
            JOIN eod_prices e ON e.stock_id = i.stock_id AND e.date = i.date
            JOIN stocks s ON s.id = i.stock_id
            WHERE i.date = :target_date AND s.is_active = true
        """),
        {"target_date": target_date},
    ).fetchone()

    near_highs = hl_row[0] if hl_row else 0
    near_lows = hl_row[1] if hl_row else 0

    if near_lows == 0 and near_highs == 0:
        s4 = 0.5
    elif near_highs >= 2 * near_lows:
        s4 = 1.0
    elif near_lows > near_highs:
        s4 = 0.0
    else:
        s4 = 0.5

    return s4, near_highs, near_lows


# ── Stability rule ────────────────────────────────────────────────────────────


def _apply_stability_rule(
    db: Session,
    target_date: date,
    raw_regime: RegimeEnum,
) -> RegimeEnum:
    """
    Regime changes only after 3 consecutive days at the new level.

    Looks up the last 2 days' regime from the scores table (regime column).
    If there is no history, the raw regime is accepted immediately.
    """
    try:
        rows = db.execute(
            text("""
                SELECT regime
                FROM market_regime_log
                WHERE date < :target_date
                ORDER BY date DESC
                LIMIT 2
            """),
            {"target_date": target_date},
        ).fetchall()
    except Exception:
        # Table may not exist yet — rollback failed transaction and skip stability rule
        db.rollback()
        logger.debug("[M2] market_regime_log not found; skipping stability rule")
        return raw_regime

    if len(rows) < 2:
        # Not enough history — accept raw regime
        return raw_regime

    prev_regimes = [r[0] for r in rows]  # most recent first

    # If the last 2 days were already at the new regime, allow the change
    if all(r == raw_regime.value for r in prev_regimes):
        return raw_regime

    # Otherwise, keep the most recent regime (no change yet)
    try:
        return RegimeEnum(prev_regimes[0])
    except ValueError:
        return raw_regime


# ── Nifty data loader ─────────────────────────────────────────────────────────


def _load_nifty_from_db(db: Session, target_date: date):
    """Load Nifty 50 index data from DB (eod_prices via stock symbol)."""
    import pandas as pd

    nifty_stock = (
        db.execute(
            text("""
                SELECT id FROM stocks
                WHERE symbol IN ('NIFTY 50', '^NSEI', 'NIFTY50')
                LIMIT 1
            """)
        ).fetchone()
    )

    if not nifty_stock:
        logger.warning("[M2] No Nifty 50 stock entry found in DB")
        return pd.DataFrame()

    rows = db.execute(
        text("""
            SELECT date, close FROM eod_prices
            WHERE stock_id = :stock_id AND date <= :target_date
            ORDER BY date
        """),
        {"stock_id": nifty_stock[0], "target_date": target_date},
    ).fetchall()

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows, columns=["date", "close"])


# ── Main entry point ──────────────────────────────────────────────────────────


def classify_regime(db: Session, target_date: date, strategy=None) -> RegimeResult:
    """
    Classify market regime for a given date.

    Requires:
      - Nifty 50 index data in DB (504+ trading days ideal)
      - indicators table populated for target_date
      - eod_prices table populated for target_date
    """
    nifty = _load_nifty_from_db(db, target_date)

    if nifty.empty or len(nifty) < 200:
        logger.warning(
            "[M2] Not enough Nifty history for regime detection (have {} rows)",
            len(nifty) if not nifty.empty else 0,
        )
        return RegimeResult(
            regime=RegimeEnum.WEAK,
            score=3.0,
            signals={"s1": 0, "s2": 0, "s3": 0.5, "s4": 0.5, "s5": 0.5, "s6": 0},
            crash_warning=False,
            max_equity_pct=50.0,
            max_positions=8,
            risk_per_trade_pct=1.0,
            exposure="Moderate (insufficient data)",
        )

    # ── Compute signals ──────────────────────────────────────────────────
    s1, s2, s5, s6, crash_warning = _compute_nifty_signals(nifty, target_date)
    s3, breadth_pct = _compute_breadth(db, target_date)
    s4, near_highs, near_lows = _compute_highs_lows(db, target_date)

    score = s1 + s2 + s3 + s4 + s5 + s6

    signals = {
        "s1": s1,
        "s2": s2,
        "s3": s3,
        "s3_pct": breadth_pct,
        "s4": s4,
        "s4_highs": near_highs,
        "s4_lows": near_lows,
        "s5": s5,
        "s6": s6,
    }

    # ── Map score → regime ────────────────────────────────────────────────
    raw_regime, equity_pct, positions, risk_pct, exposure = _score_to_regime(
        score, crash_warning
    )

    # ── Stability rule ────────────────────────────────────────────────────
    regime = _apply_stability_rule(db, target_date, raw_regime)

    # If stability rule changed the regime, recalculate allocation params
    if regime != raw_regime:
        _, equity_pct, positions, risk_pct, exposure = _score_to_regime(
            score=score, crash_warning=False
        )
        # Re-derive from the stabilised regime
        for min_s, max_s, r, eq, pos, rsk, exp in _REGIME_TABLE:
            if r == regime:
                equity_pct, positions, risk_pct, exposure = eq, pos, rsk, exp
                break
        exposure += " (stabilised)"

    result = RegimeResult(
        regime=regime,
        score=round(score, 1),
        signals=signals,
        crash_warning=crash_warning,
        max_equity_pct=equity_pct,
        max_positions=positions,
        risk_per_trade_pct=risk_pct,
        exposure=exposure,
    )

    logger.info(
        "[M2] Regime: {} | Score: {:.1f}/6 | Crash: {} | "
        "S1={} S2={} S3={} S4={} S5={} S6={} | "
        "Equity: {}% | Positions: {} | Risk: {}% | {}",
        regime.value,
        score,
        crash_warning,
        s1,
        s2,
        s3,
        s4,
        s5,
        s6,
        equity_pct,
        positions,
        risk_pct,
        exposure,
    )

    return result
