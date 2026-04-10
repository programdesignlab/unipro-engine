"""
v16 Monster Stock Detection — based on Bessembinder 2018.

Top 4% of stocks drive all net market wealth creation. This module identifies
potential monster stocks early and overrides exit rules to let them run.

Score 0-100 across 7 criteria:
  +25  RS rank >= 90th percentile
  +20  3+ prior institutional accumulation bases (consolidation count)
  +20  70%+ of weekly closes positive (momentum quality)
  +15  Sector rank = #1
  +10  EPS acceleration 4+ consecutive quarters
  +10  Each successive base shallower (base depth contracting)
  +10  Sector outperformance >= 2x over 6 months

Activation: score >= 80 AND gain >= 40% → override to Phase 4 exit rules.
Gain < 40%: score tracked but does not change exit phase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.core.strategy import MonsterConfig


@dataclass
class MonsterResult:
    stock_id: int
    symbol: str
    score: int               # 0-100
    meets_threshold: bool    # score >= threshold
    override_active: bool    # meets_threshold AND gain >= gain_gate
    components: dict[str, int] = field(default_factory=dict)


def _check_rs_elite(db: Session, stock_id: int, target_date: date) -> int:
    """RS rank >= 90th percentile → +25."""
    row = db.execute(
        text("""
            SELECT rs_rank FROM indicators
            WHERE stock_id = :sid AND date = :d
        """),
        {"sid": stock_id, "d": target_date},
    ).fetchone()

    total = db.execute(
        text("SELECT COUNT(*) FROM indicators WHERE date = :d AND rs_rank IS NOT NULL"),
        {"d": target_date},
    ).scalar()

    if not row or row[0] is None or not total or total == 0:
        return 0

    percentile = ((total - row[0]) / total) * 100
    return 25 if percentile >= 90 else 0


def _check_consolidation_count(db: Session, stock_id: int, target_date: date) -> int:
    """3+ prior institutional accumulation bases → +20.

    Proxy: count distinct signals (confirmed breakouts) in last 2 years.
    """
    count = db.execute(
        text("""
            SELECT COUNT(*) FROM signals
            WHERE stock_id = :sid AND status = 'Confirmed'
              AND signal_date >= :start AND signal_date <= :d
        """),
        {
            "sid": stock_id,
            "d": target_date,
            "start": date(target_date.year - 2, target_date.month, target_date.day),
        },
    ).scalar()

    return 20 if (count or 0) >= 3 else 0


def _check_momentum_quality(db: Session, stock_id: int, target_date: date) -> int:
    """70%+ of weekly closes positive → +20."""
    row = db.execute(
        text("""
            SELECT mom_quality FROM indicators
            WHERE stock_id = :sid AND date = :d
        """),
        {"sid": stock_id, "d": target_date},
    ).fetchone()

    if row and row[0] is not None and row[0] >= 0.70:
        return 20
    return 0


def _check_sector_leader(db: Session, stock_id: int, target_date: date) -> int:
    """Stock's sector is ranked #1 → +15.

    Proxy: check if sector has highest avg RS score.
    """
    row = db.execute(
        text("""
            SELECT s.sector FROM stocks s WHERE s.id = :sid
        """),
        {"sid": stock_id},
    ).fetchone()

    if not row or not row[0]:
        return 0

    sector = row[0]

    # Get sector ranking
    top_sector = db.execute(
        text("""
            SELECT s.sector, AVG(i.rs_score) AS avg_rs
            FROM indicators i
            JOIN stocks s ON s.id = i.stock_id
            WHERE i.date = :d AND s.is_active = true AND i.rs_score IS NOT NULL
            GROUP BY s.sector
            HAVING COUNT(*) >= 2
            ORDER BY AVG(i.rs_score) DESC NULLS LAST
            LIMIT 1
        """),
        {"d": target_date},
    ).fetchone()

    if top_sector and top_sector[0] == sector:
        return 15
    return 0


def _check_eps_acceleration_sustained(db: Session, stock_id: int, target_date: date) -> int:
    """EPS acceleration 4+ consecutive quarters → +10."""
    rows = db.execute(
        text("""
            SELECT eps_yoy_growth FROM fundamentals
            WHERE stock_id = :sid AND reporting_date <= :d
              AND eps_yoy_growth IS NOT NULL
            ORDER BY quarter DESC LIMIT 5
        """),
        {"sid": stock_id, "d": target_date},
    ).fetchall()

    if len(rows) < 4:
        return 0

    growths = [r[0] for r in rows]
    # Check 4 consecutive quarters of increasing growth
    for i in range(len(growths) - 3):
        window = growths[i:i + 4]
        if all(window[j] > window[j + 1] for j in range(3)) and window[0] > 0:
            return 10
    return 0


def _check_base_depth_contracting(db: Session, stock_id: int, target_date: date) -> int:
    """Each successive base shallower than prior → +10.

    Proxy: compare recent ATR vs earlier ATR — if ATR declining, bases are tighter.
    """
    rows = db.execute(
        text("""
            SELECT atr FROM indicators
            WHERE stock_id = :sid AND date <= :d AND atr IS NOT NULL
            ORDER BY date DESC LIMIT 60
        """),
        {"sid": stock_id, "d": target_date},
    ).fetchall()

    if len(rows) < 40:
        return 0

    recent_atr = sum(r[0] for r in rows[:20]) / 20
    earlier_atr = sum(r[0] for r in rows[20:40]) / 20

    if earlier_atr > 0 and recent_atr < earlier_atr * 0.80:
        return 10
    return 0


def _check_sector_outperformance(db: Session, stock_id: int, target_date: date) -> int:
    """Sector outperformance >= 2x over 6 months → +10."""
    row = db.execute(
        text("""
            SELECT i.rs_score, s.sector FROM indicators i
            JOIN stocks s ON s.id = i.stock_id
            WHERE i.stock_id = :sid AND i.date = :d
        """),
        {"sid": stock_id, "d": target_date},
    ).fetchone()

    if not row or row[0] is None or not row[1]:
        return 0

    stock_rs = row[0]
    sector = row[1]

    sector_avg = db.execute(
        text("""
            SELECT AVG(i.rs_score) FROM indicators i
            JOIN stocks s ON s.id = i.stock_id
            WHERE i.date = :d AND s.sector = :sector AND i.rs_score IS NOT NULL
        """),
        {"d": target_date, "sector": sector},
    ).scalar()

    if sector_avg and sector_avg > 0 and stock_rs >= sector_avg * 2:
        return 10
    return 0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def calculate_monster_score(
    db: Session,
    stock_id: int,
    symbol: str,
    target_date: date,
    gain_pct: float = 0.0,
    config: MonsterConfig | None = None,
) -> MonsterResult:
    """
    Calculate monster stock score (0-100) and determine if override is active.

    Activation requires:
    1. Score >= threshold (default 80)
    2. Gain >= gain_gate (default 40%)
    Both conditions must be true for the exit phase override.
    """
    if config is None or not config.enabled:
        return MonsterResult(
            stock_id=stock_id, symbol=symbol, score=0,
            meets_threshold=False, override_active=False,
        )

    threshold = config.score_threshold
    gain_gate = config.gain_gate

    # Run all criteria
    components = {
        "rs_rank_elite": _check_rs_elite(db, stock_id, target_date),
        "consolidation_count": _check_consolidation_count(db, stock_id, target_date),
        "momentum_quality": _check_momentum_quality(db, stock_id, target_date),
        "sector_leader": _check_sector_leader(db, stock_id, target_date),
        "eps_acceleration_sustained": _check_eps_acceleration_sustained(db, stock_id, target_date),
        "base_depth_contracting": _check_base_depth_contracting(db, stock_id, target_date),
        "sector_outperformance": _check_sector_outperformance(db, stock_id, target_date),
    }

    score = sum(components.values())
    meets_threshold = score >= threshold
    override_active = meets_threshold and gain_pct >= gain_gate

    if meets_threshold:
        logger.info(
            "{}: monster score {} (threshold {}) — override {}",
            symbol, score, threshold,
            "ACTIVE" if override_active else f"INACTIVE (gain {gain_pct*100:.0f}% < gate {gain_gate*100:.0f}%)",
        )

    return MonsterResult(
        stock_id=stock_id,
        symbol=symbol,
        score=score,
        meets_threshold=meets_threshold,
        override_active=override_active,
        components=components,
    )
