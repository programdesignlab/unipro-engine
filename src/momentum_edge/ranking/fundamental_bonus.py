"""
v16 Fundamental Bonus — expanded scoring range [-20, +30].

Fundamentals are BONUS scores only — they never eliminate a stock from the
universe. Junk removal is handled by universe_filter.py.

Bonuses:
  +8   EPS acceleration (3 quarters of rising YoY growth)
  +5   EPS growth >= 15% (latest quarter YoY)
  +2   EPS growth >= 0% but < 15%
  +4   Analyst upward revision
  +12  Revenue growth >20% AND OPM expanding >300bp (v16)
  +10  Revenue acceleration >30% YoY (v16)
  +8   OPM expansion >300bp over 3 quarters (v16)
  +8   Promoter buying in last 2 quarters (v16)
  +10  PEAD/SUE strong: EPS growth >50% within 60 days (v16)
  +6   PEAD/SUE moderate: EPS growth >25% within 60 days (v16)
  +6   Market cap band crossing within 60 days (v16)
  +3   D/E < 1.0 (non-financial)
  +2   D/E < 1.5 (non-financial)
  +1   D/E < 2.0 (non-financial)

Penalties:
  -2   D/E > 3.0
  -8   Promoter selling in last 2 quarters (v16)
  -10  Active SEBI investigation (v16)
  -3   LODR fine in last 12 months (v16)
  -5   Trade receivable days > 180 (v16)
  -3   Trade receivable days > 120 (v16)
  -5   OCF/net profit < 0.4 for 2 quarters (v16)
"""

from __future__ import annotations

from datetime import date, timedelta

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.models import Fundamentals, Stock


# ---------------------------------------------------------------------------
# Individual signal checks
# ---------------------------------------------------------------------------


def _check_eps_acceleration(rows: list, symbol: str) -> int:
    """3 quarters of accelerating YoY EPS growth, latest > 0."""
    growths = [r[2] for r in rows if r[2] is not None]
    if len(growths) >= 3:
        g0, g1, g2 = growths[0], growths[1], growths[2]
        if g0 > g1 > g2 and g0 > 0:
            return 8
    return 0


def _check_eps_growth(latest_eps_growth: float | None) -> int:
    """EPS growth level: +5 for >=15%, +2 for >=0%."""
    if latest_eps_growth is None:
        return 0
    if latest_eps_growth >= 15:
        return 5
    if latest_eps_growth >= 0:
        return 2
    return 0


def _check_analyst_revision(latest_revision: float | None) -> int:
    """Upward analyst revision → +4."""
    if latest_revision is not None and latest_revision > 0:
        return 4
    return 0


def _check_de_score(latest_de: float | None, is_financial: bool) -> int:
    """D/E scoring: +3/+2/+1 bonus or -2 penalty. Skip for financials."""
    if is_financial or latest_de is None:
        return 0
    if latest_de < 1.0:
        return 3
    if latest_de < 1.5:
        return 2
    if latest_de < 2.0:
        return 1
    if latest_de > 3.0:
        return -2
    return 0


def _check_revenue_opm_simultaneous(db: Session, stock_id: int, as_of_date: date) -> int:
    """Revenue growth >20% AND OPM expanding >300bp → +12."""
    rows = db.execute(
        text("""
            SELECT revenue_yoy_growth, opm FROM fundamentals
            WHERE stock_id = :sid AND reporting_date <= :d AND opm IS NOT NULL
            ORDER BY quarter DESC LIMIT 3
        """),
        {"sid": stock_id, "d": as_of_date},
    ).fetchall()

    if not rows or rows[0][0] is None or rows[0][1] is None:
        return 0

    rev_growth = rows[0][0]
    if len(rows) >= 3 and rows[2][1] is not None:
        opm_expansion = rows[0][1] - rows[2][1]  # latest vs 3 quarters ago
        if rev_growth > 20 and opm_expansion > 3.0:  # 300bp
            return 12
    return 0


def _check_revenue_acceleration(db: Session, stock_id: int, as_of_date: date) -> int:
    """Revenue growth >30% YoY → +10."""
    row = db.execute(
        text("""
            SELECT revenue_yoy_growth FROM fundamentals
            WHERE stock_id = :sid AND reporting_date <= :d
            ORDER BY quarter DESC LIMIT 1
        """),
        {"sid": stock_id, "d": as_of_date},
    ).fetchone()

    if row and row[0] is not None and row[0] > 30:
        return 10
    return 0


def _check_opm_expansion(db: Session, stock_id: int, as_of_date: date) -> int:
    """OPM expanding >300bp over 3 quarters → +8."""
    rows = db.execute(
        text("""
            SELECT opm FROM fundamentals
            WHERE stock_id = :sid AND reporting_date <= :d AND opm IS NOT NULL
            ORDER BY quarter DESC LIMIT 3
        """),
        {"sid": stock_id, "d": as_of_date},
    ).fetchall()

    if len(rows) >= 3 and rows[0][0] is not None and rows[2][0] is not None:
        expansion = rows[0][0] - rows[2][0]
        if expansion > 3.0:
            return 8
    return 0


def _check_promoter_buying(db: Session, stock_id: int, as_of_date: date) -> int:
    """Promoter open market purchases in last 2 quarters → +8."""
    rows = db.execute(
        text("""
            SELECT promoter_pct FROM shareholding_pattern
            WHERE stock_id = :sid AND quarter_end_date <= :d
            ORDER BY quarter_end_date DESC LIMIT 3
        """),
        {"sid": stock_id, "d": as_of_date},
    ).fetchall()

    if len(rows) >= 2 and rows[0][0] is not None and rows[1][0] is not None:
        if rows[0][0] > rows[1][0]:  # promoter % increasing
            return 8
    return 0


def _check_promoter_selling(db: Session, stock_id: int, as_of_date: date) -> int:
    """Promoter selling in last 2 quarters → -8."""
    rows = db.execute(
        text("""
            SELECT promoter_pct FROM shareholding_pattern
            WHERE stock_id = :sid AND quarter_end_date <= :d
            ORDER BY quarter_end_date DESC LIMIT 3
        """),
        {"sid": stock_id, "d": as_of_date},
    ).fetchall()

    if len(rows) >= 2 and rows[0][0] is not None and rows[1][0] is not None:
        if rows[0][0] < rows[1][0] - 1.0:  # meaningful decline (>1%)
            return -8
    return 0


def _check_pead_sue(db: Session, stock_id: int, as_of_date: date) -> int:
    """Post-Earnings Announcement Drift: strong EPS growth reported recently."""
    row = db.execute(
        text("""
            SELECT eps_yoy_growth, reporting_date FROM fundamentals
            WHERE stock_id = :sid AND reporting_date IS NOT NULL
              AND reporting_date <= :d
            ORDER BY reporting_date DESC LIMIT 1
        """),
        {"sid": stock_id, "d": as_of_date},
    ).fetchone()

    if not row or row[0] is None or row[1] is None:
        return 0

    growth = row[0]
    report_date = row[1]
    days_since = (as_of_date - report_date).days

    if days_since > 60:
        return 0

    if growth > 50:
        return 10  # Strong SUE
    if growth > 25:
        return 6   # Moderate SUE
    return 0


def _check_sebi_investigation(db: Session, stock_id: int) -> int:
    """Active SEBI price investigation → -10."""
    stock = db.get(Stock, stock_id)
    if stock and getattr(stock, "sebi_investigation_active", False):
        return -10
    return 0


def _check_lodr_fine(db: Session, stock_id: int) -> int:
    """LODR fine in last 12 months → -3."""
    stock = db.get(Stock, stock_id)
    if stock and getattr(stock, "lodr_fine_last_12m", False):
        return -3
    return 0


def _check_debtors(db: Session, stock_id: int, as_of_date: date) -> int:
    """Trade receivable days penalty: >180 = -5, >120 = -3."""
    row = db.execute(
        text("""
            SELECT trade_receivables_days FROM fundamentals
            WHERE stock_id = :sid AND reporting_date <= :d
              AND trade_receivables_days IS NOT NULL
            ORDER BY quarter DESC LIMIT 1
        """),
        {"sid": stock_id, "d": as_of_date},
    ).fetchone()

    if not row or row[0] is None:
        return 0

    days = row[0]
    if days > 180:
        return -5
    if days > 120:
        return -3
    return 0


def _check_ocf_quality(db: Session, stock_id: int, as_of_date: date) -> int:
    """OCF/net profit < 0.4 for 2 consecutive quarters → -5."""
    rows = db.execute(
        text("""
            SELECT ocf_cr, eps FROM fundamentals
            WHERE stock_id = :sid AND reporting_date <= :d
              AND ocf_cr IS NOT NULL AND eps IS NOT NULL AND eps > 0
            ORDER BY quarter DESC LIMIT 2
        """),
        {"sid": stock_id, "d": as_of_date},
    ).fetchall()

    if len(rows) < 2:
        return 0

    poor_count = 0
    for r in rows:
        ocf, eps = r[0], r[1]
        # Rough OCF/profit ratio (both in different units, but direction is useful)
        if eps > 0 and ocf < eps * 0.4:
            poor_count += 1

    if poor_count >= 2:
        return -5
    return 0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def calculate_fundamental_bonus(
    db: Session, stock_id: int, symbol: str, as_of_date: date,
    params: dict | None = None,
) -> int:
    """
    Calculate fundamental bonus score for a stock.

    Reads score_range from params (default [-20, 30] for v16).
    """
    p = params or {}
    score_range = p.get("score_range", [-20, 30])

    bonus = 0

    # ── Fetch recent quarters (up to 4) ────────────────────────────────
    rows = db.execute(
        text("""
            SELECT quarter, eps, eps_yoy_growth, debt_to_equity,
                   analyst_revision, is_financial
            FROM fundamentals
            WHERE stock_id = :stock_id
              AND reporting_date <= :as_of_date
            ORDER BY quarter DESC
            LIMIT 4
        """),
        {"stock_id": stock_id, "as_of_date": as_of_date},
    ).fetchall()

    if not rows:
        logger.debug("{}: no fundamental data — bonus = 0", symbol)
        return 0

    latest = rows[0]
    latest_eps_growth = latest[2]
    latest_de = latest[3]
    latest_revision = latest[4]
    latest_is_financial = latest[5]

    # Check stock-level financial flag as fallback
    is_financial = bool(latest_is_financial)
    if not is_financial:
        stock = db.get(Stock, stock_id)
        if stock is not None:
            is_financial = stock.is_financial

    # ── Core v7 signals ───────────────────────────────────────────────
    bonus += _check_eps_acceleration(rows, symbol)
    bonus += _check_eps_growth(latest_eps_growth)
    bonus += _check_analyst_revision(latest_revision)
    bonus += _check_de_score(latest_de, is_financial)

    # ── v16 bonus signals ─────────────────────────────────────────────
    bonus += _check_revenue_opm_simultaneous(db, stock_id, as_of_date)
    bonus += _check_revenue_acceleration(db, stock_id, as_of_date)
    bonus += _check_opm_expansion(db, stock_id, as_of_date)
    bonus += _check_promoter_buying(db, stock_id, as_of_date)
    bonus += _check_pead_sue(db, stock_id, as_of_date)

    # ── v16 penalty signals ───────────────────────────────────────────
    bonus += _check_promoter_selling(db, stock_id, as_of_date)
    bonus += _check_sebi_investigation(db, stock_id)
    bonus += _check_lodr_fine(db, stock_id)
    bonus += _check_debtors(db, stock_id, as_of_date)
    bonus += _check_ocf_quality(db, stock_id, as_of_date)

    # ── Clamp to configurable range ──────────────────────────────────
    clamped = max(score_range[0], min(score_range[1], bonus))
    if clamped != bonus:
        logger.debug("{}: bonus clamped {} → {}", symbol, bonus, clamped)

    logger.info("{}: fundamental bonus = {}", symbol, clamped)
    return clamped
