"""
v7 Fundamental Bonus — replaces canslim_score.py.

Fundamentals are BONUS scores only — they never eliminate a stock from the
universe. Junk removal is handled by universe_filter.py.

Scoring (max +20, min -5):
  +8  EPS acceleration (3 quarters of accelerating YoY growth)
  +5  EPS growth >= 15% (latest quarter YoY)
  +2  EPS growth >= 0% but < 15%
  +4  Analyst upward revision (skip if NULL)
  +3  D/E < 1.0  (skip if is_financial)
  +2  D/E < 1.5
  +1  D/E < 2.0
  -2  D/E > 3.0  (penalty, not elimination)
"""

from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.models import Fundamentals, Stock


def calculate_fundamental_bonus(
    db: Session, stock_id: int, symbol: str, as_of_date: date
) -> int:
    """
    Calculate fundamental bonus score for a stock.

    Returns an integer clamped to [-5, 20].
    """
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
    latest_eps_growth = latest[2]   # eps_yoy_growth
    latest_de = latest[3]           # debt_to_equity
    latest_revision = latest[4]     # analyst_revision
    latest_is_financial = latest[5] # is_financial

    # ── EPS acceleration (+8) ──────────────────────────────────────────
    # Need at least 3 quarters with eps_yoy_growth data
    growths = [r[2] for r in rows if r[2] is not None]

    if len(growths) >= 3:
        g0, g1, g2 = growths[0], growths[1], growths[2]
        if g0 > g1 > g2 and g0 > 0:
            bonus += 8
            logger.debug(
                "{}: EPS acceleration +8 (g0={:.1f}, g1={:.1f}, g2={:.1f})",
                symbol, g0, g1, g2,
            )

    # ── EPS growth level (+5 or +2) ────────────────────────────────────
    if latest_eps_growth is not None:
        if latest_eps_growth >= 15:
            bonus += 5
            logger.debug("{}: EPS growth {:.1f}% >= 15% → +5", symbol, latest_eps_growth)
        elif latest_eps_growth >= 0:
            bonus += 2
            logger.debug("{}: EPS growth {:.1f}% >= 0% → +2", symbol, latest_eps_growth)

    # ── Analyst upward revision (+4) ───────────────────────────────────
    if latest_revision is not None and latest_revision > 0:
        bonus += 4
        logger.debug("{}: analyst upward revision {:.2f} → +4", symbol, latest_revision)

    # ── Debt-to-Equity scoring (+3/+2/+1 or -2 penalty) ───────────────
    # Skip D/E scoring entirely for financials (banks, NBFCs, insurance)
    is_financial = bool(latest_is_financial)

    # Also check stock-level flag as fallback
    if not is_financial:
        stock = db.get(Stock, stock_id)
        if stock is not None:
            is_financial = stock.is_financial

    if is_financial:
        logger.debug("{}: financial sector — D/E scoring skipped", symbol)
    elif latest_de is not None:
        if latest_de < 1.0:
            bonus += 3
            logger.debug("{}: D/E {:.2f} < 1.0 → +3", symbol, latest_de)
        elif latest_de < 1.5:
            bonus += 2
            logger.debug("{}: D/E {:.2f} < 1.5 → +2", symbol, latest_de)
        elif latest_de < 2.0:
            bonus += 1
            logger.debug("{}: D/E {:.2f} < 2.0 → +1", symbol, latest_de)
        elif latest_de > 3.0:
            bonus -= 2
            logger.debug("{}: D/E {:.2f} > 3.0 → -2 penalty", symbol, latest_de)

    # ── Clamp to [-5, 20] ─────────────────────────────────────────────
    clamped = max(-5, min(20, bonus))
    if clamped != bonus:
        logger.debug("{}: bonus clamped {} → {}", symbol, bonus, clamped)

    logger.info("{}: fundamental bonus = {}", symbol, clamped)
    return clamped
