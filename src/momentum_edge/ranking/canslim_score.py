"""
M5 — CANSLIM Fundamental Filter (max 25 pts).

Hard filters (stock eliminated if fails):
  - Quarterly EPS growth (YoY) >= 25%
  - Revenue growth (YoY) >= 20%
  - ROE >= 15%

Soft filters (score penalty):
  - Profit margin trend (expanding over recent quarters)
  - Debt-to-equity < 1.0

Reads from the fundamentals table (latest quarter per stock).
"""

from dataclasses import dataclass
from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class CANSLIMResult:
    symbol: str
    passes: bool
    score: float  # max 25
    eps_growth: float | None
    revenue_growth: float | None
    roe: float | None
    net_margin: float | None
    debt_to_equity: float | None
    fail_reason: str | None


def apply_canslim_filter(db: Session, stock_id: int, symbol: str) -> CANSLIMResult:
    """
    Apply CANSLIM filter for a single stock.
    Returns CANSLIMResult with pass/fail and score (max 25 pts).
    """
    # Get latest fundamental data
    row = db.execute(
        text("""
            SELECT eps_yoy_growth, revenue_yoy_growth, roe, net_margin, debt_to_equity
            FROM fundamentals
            WHERE stock_id = :stock_id
            ORDER BY quarter DESC
            LIMIT 1
        """),
        {"stock_id": stock_id},
    ).fetchone()

    if not row:
        return CANSLIMResult(
            symbol=symbol, passes=False, score=0.0,
            eps_growth=None, revenue_growth=None, roe=None,
            net_margin=None, debt_to_equity=None,
            fail_reason="no fundamental data",
        )

    eps_growth = row[0]      # %
    rev_growth = row[1]      # %
    roe = row[2]             # %
    net_margin = row[3]      # %
    de_ratio = row[4]

    # Hard filters
    fails = []
    if eps_growth is not None and eps_growth < 25:
        fails.append(f"EPS growth {eps_growth:.0f}% < 25%")
    if rev_growth is not None and rev_growth < 20:
        fails.append(f"Revenue growth {rev_growth:.0f}% < 20%")
    if roe is not None and roe < 15:
        fails.append(f"ROE {roe:.0f}% < 15%")

    # If any hard data is missing, don't eliminate — just penalize
    if fails:
        return CANSLIMResult(
            symbol=symbol, passes=False, score=0.0,
            eps_growth=eps_growth, revenue_growth=rev_growth,
            roe=roe, net_margin=net_margin, debt_to_equity=de_ratio,
            fail_reason="; ".join(fails),
        )

    # Scoring (stock passed hard filters)
    score = 0.0

    # EPS growth: 0-8 pts. 25% = 4, 50%+ = 8
    if eps_growth is not None:
        score += min(8.0, max(0.0, eps_growth / 50.0 * 8.0))
    else:
        score += 4.0  # neutral if missing

    # Revenue growth: 0-6 pts. 20% = 3, 40%+ = 6
    if rev_growth is not None:
        score += min(6.0, max(0.0, rev_growth / 40.0 * 6.0))
    else:
        score += 3.0

    # ROE: 0-5 pts. 15% = 2.5, 30%+ = 5
    if roe is not None:
        score += min(5.0, max(0.0, roe / 30.0 * 5.0))
    else:
        score += 2.5

    # Net margin (soft): 0-3 pts
    if net_margin is not None and net_margin > 0:
        score += min(3.0, net_margin / 10.0 * 3.0)
    else:
        score += 1.0

    # D/E ratio (soft): 0-3 pts. <0.5 = 3, >1.0 = 0
    if de_ratio is not None:
        if de_ratio < 0.5:
            score += 3.0
        elif de_ratio < 1.0:
            score += 1.5
        # else: 0
    else:
        score += 1.5  # neutral if missing

    return CANSLIMResult(
        symbol=symbol, passes=True, score=min(25.0, round(score, 1)),
        eps_growth=eps_growth, revenue_growth=rev_growth,
        roe=roe, net_margin=net_margin, debt_to_equity=de_ratio,
        fail_reason=None,
    )
