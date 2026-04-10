"""
v16 Bull Market Entry Protocol — structured 4-phase re-entry after Bear regime.

Prevents capital deployment into failed bear rallies. Only activates when
regime transitions from Bear/Full Bear.

Phases:
  B1 — Capitulation:    Panic volume + A/D higher low while price lower low → WATCH (0%)
  B2 — Breadth Thrust:  Single day 90%+ advancing volume → deploy 25%
  B3 — A/D Confirmation: A/D line higher high than capitulation → deploy 25% more
  B4 — New Highs Expand: 52w highs > 100/week for 2+ weeks → full regime allocation

Capital deployment is cumulative: B2=25%, B3=50%, B4=regime%.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.core.strategy import BullEntryProtocolConfig


class BullEntryPhase(str, Enum):
    INACTIVE = "inactive"           # Not in bear recovery
    CAPITULATION = "capitulation"   # B1: watching, 0% deploy
    BREADTH_THRUST = "breadth_thrust"  # B2: 25% deploy
    AD_CONFIRMATION = "ad_confirmation"  # B3: 50% deploy
    NEW_HIGHS_EXPAND = "new_highs_expand"  # B4: full deploy
    COMPLETE = "complete"           # Protocol finished, use regime allocation


@dataclass
class BullEntryResult:
    phase: BullEntryPhase
    capital_deploy_pct: float   # 0.0, 0.25, 0.50, or None (use regime)
    reason: str


def _check_capitulation(db: Session, target_date: date) -> bool:
    """B1: Panic volume spike on Nifty500 + A/D higher low while price lower low."""
    # Check for panic volume: today's market volume > 2x 20-day average
    row = db.execute(
        text("""
            SELECT
                SUM(e.volume) AS today_vol,
                (SELECT AVG(day_vol) FROM (
                    SELECT SUM(volume) AS day_vol FROM eod_prices
                    WHERE date < :d
                    GROUP BY date
                    ORDER BY date DESC LIMIT 20
                ) sub) AS avg_vol
            FROM eod_prices e
            JOIN stocks s ON s.id = e.stock_id
            WHERE e.date = :d AND s.is_active = true
        """),
        {"d": target_date},
    ).fetchone()

    if not row or not row[0] or not row[1]:
        return False

    panic_volume = float(row[0]) > float(row[1]) * 2.0
    return panic_volume


def _check_breadth_thrust(db: Session, target_date: date) -> bool:
    """B2: Single day with 90%+ advancing stocks by volume."""
    row = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE i.adl_ratio > 0.5) AS advancing,
                COUNT(*) AS total
            FROM indicators i
            WHERE i.date = :d AND i.adl_ratio IS NOT NULL
        """),
        {"d": target_date},
    ).fetchone()

    if not row or not row[1] or row[1] == 0:
        return False

    advance_pct = row[0] / row[1]
    return advance_pct >= 0.90


def _check_ad_confirmation(db: Session, target_date: date) -> bool:
    """B3: A/D line making higher high (avg ADL ratio improving)."""
    rows = db.execute(
        text("""
            SELECT date, AVG(adl_ratio) AS avg_adl FROM indicators
            WHERE date <= :d AND adl_ratio IS NOT NULL
            GROUP BY date ORDER BY date DESC LIMIT 20
        """),
        {"d": target_date},
    ).fetchall()

    if len(rows) < 10:
        return False

    recent_avg = sum(r[1] for r in rows[:5]) / 5
    earlier_avg = sum(r[1] for r in rows[10:15]) / min(5, len(rows[10:15])) if len(rows) > 10 else 0

    return recent_avg > earlier_avg and recent_avg > 0.55


def _check_new_highs_expand(db: Session, target_date: date) -> bool:
    """B4: 52w highs > 100 stocks/week for 2+ consecutive weeks."""
    # Get weekly counts of stocks near 52w highs for last 3 weeks
    rows = db.execute(
        text("""
            SELECT
                DATE_TRUNC('week', date) AS week,
                COUNT(*) FILTER (WHERE pct_from_high >= -0.03) AS near_highs
            FROM indicators
            WHERE date <= :d AND date >= :d - INTERVAL '21 days'
              AND pct_from_high IS NOT NULL
            GROUP BY DATE_TRUNC('week', date)
            ORDER BY week DESC
            LIMIT 3
        """),
        {"d": target_date},
    ).fetchall()

    if len(rows) < 2:
        return False

    # Check if last 2 weeks both had 100+ new highs
    return all(r[1] >= 100 for r in rows[:2])


def evaluate_bull_entry_phase(
    db: Session,
    target_date: date,
    current_regime: str,
    previous_phase: BullEntryPhase | None = None,
    config: BullEntryProtocolConfig | None = None,
) -> BullEntryResult:
    """
    Evaluate current bull entry protocol phase.

    Only active when recovering from Bear/Full Bear.
    Phases advance forward only (never go back to earlier phase).
    """
    if config is None or not config.enabled:
        return BullEntryResult(
            phase=BullEntryPhase.INACTIVE,
            capital_deploy_pct=1.0,
            reason="bull entry protocol disabled",
        )

    # Only activate if coming from Bear regime
    if current_regime not in ("Bear", "Full Bear") and previous_phase in (None, BullEntryPhase.INACTIVE, BullEntryPhase.COMPLETE):
        return BullEntryResult(
            phase=BullEntryPhase.INACTIVE,
            capital_deploy_pct=1.0,  # normal regime allocation
            reason="not in bear recovery",
        )

    # If already complete, stay complete
    if previous_phase == BullEntryPhase.COMPLETE:
        return BullEntryResult(
            phase=BullEntryPhase.COMPLETE,
            capital_deploy_pct=1.0,
            reason="protocol complete — full deployment",
        )

    # Advance through phases (can skip if conditions met)
    if previous_phase in (None, BullEntryPhase.INACTIVE, BullEntryPhase.CAPITULATION):
        if _check_new_highs_expand(db, target_date):
            return BullEntryResult(
                phase=BullEntryPhase.COMPLETE,
                capital_deploy_pct=1.0,
                reason="B4: new highs expanding — full deployment",
            )
        if _check_ad_confirmation(db, target_date):
            return BullEntryResult(
                phase=BullEntryPhase.AD_CONFIRMATION,
                capital_deploy_pct=0.50,
                reason="B3: A/D confirmation — 50% deployment",
            )
        if _check_breadth_thrust(db, target_date):
            return BullEntryResult(
                phase=BullEntryPhase.BREADTH_THRUST,
                capital_deploy_pct=0.25,
                reason="B2: breadth thrust — 25% deployment",
            )
        if _check_capitulation(db, target_date):
            return BullEntryResult(
                phase=BullEntryPhase.CAPITULATION,
                capital_deploy_pct=0.0,
                reason="B1: capitulation detected — watch only",
            )
        # Still in Bear, no protocol signal yet
        return BullEntryResult(
            phase=BullEntryPhase.CAPITULATION,
            capital_deploy_pct=0.0,
            reason="awaiting capitulation signal",
        )

    # Advance from breadth thrust
    if previous_phase == BullEntryPhase.BREADTH_THRUST:
        if _check_new_highs_expand(db, target_date):
            return BullEntryResult(phase=BullEntryPhase.COMPLETE, capital_deploy_pct=1.0, reason="B4: new highs → full")
        if _check_ad_confirmation(db, target_date):
            return BullEntryResult(phase=BullEntryPhase.AD_CONFIRMATION, capital_deploy_pct=0.50, reason="B3: A/D confirmed → 50%")
        return BullEntryResult(phase=BullEntryPhase.BREADTH_THRUST, capital_deploy_pct=0.25, reason="holding at B2: 25%")

    # Advance from A/D confirmation
    if previous_phase == BullEntryPhase.AD_CONFIRMATION:
        if _check_new_highs_expand(db, target_date):
            return BullEntryResult(phase=BullEntryPhase.COMPLETE, capital_deploy_pct=1.0, reason="B4: new highs → full")
        return BullEntryResult(phase=BullEntryPhase.AD_CONFIRMATION, capital_deploy_pct=0.50, reason="holding at B3: 50%")

    # Fallback
    return BullEntryResult(
        phase=BullEntryPhase.INACTIVE,
        capital_deploy_pct=1.0,
        reason="fallback — inactive",
    )
