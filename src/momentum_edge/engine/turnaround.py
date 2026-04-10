"""
v16 Turnaround Watch — fires 1-3 quarters before the EPS hard block clears.

Conditions (all must be true):
  1. EPS was negative in >= 2 of last 8 quarters (genuine loss phase)
  2. EPS improving monotonically for last 4 quarters
  3. Most recent quarter EPS > 0 (first positive quarter)
  4. Revenue growing > 10% YoY (real recovery, not cost-cutting)
  5. EPS block still active (< 2 of last 4 quarters positive)

Suppression (any → suppress from dashboard):
  - Promoter pledge > threshold
  - SEBI fine active
  - Business pivots >= 3 in 5 years
  - OCF negative 3+ of 4 quarters

Validated: GE Vernova T&D — fires at Rs 220 (June 2023); entry at Rs 280-320 (Sep-Oct 2023).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.core.strategy import TurnaroundWatchConfig


@dataclass
class TurnaroundCandidate:
    stock_id: int
    symbol: str
    eps_trend: list[float | None]     # last 8 quarters
    revenue_growth_yoy: float | None
    suppressed: bool
    suppression_reason: str | None


def _check_turnaround_conditions(
    db: Session,
    stock_id: int,
    symbol: str,
    target_date: date,
    config: TurnaroundWatchConfig,
) -> TurnaroundCandidate | None:
    """Check if a stock qualifies for turnaround watch."""
    conds = config.conditions

    # Fetch last 8 quarters of EPS
    rows = db.execute(
        text("""
            SELECT quarter, eps, revenue_yoy_growth, reporting_date
            FROM fundamentals
            WHERE stock_id = :sid AND reporting_date <= :d
            ORDER BY quarter DESC LIMIT :n
        """),
        {"sid": stock_id, "d": target_date, "n": conds.lookback_quarters},
    ).fetchall()

    if len(rows) < conds.monotonic_improvement_quarters:
        return None

    eps_values = [r[1] for r in rows]

    # Condition 1: EPS negative in >= N of last 8 quarters
    negative_count = sum(1 for e in eps_values if e is not None and e < 0)
    if negative_count < conds.min_negative_quarters:
        return None

    # Condition 2: EPS improving monotonically for last 4 quarters
    recent = eps_values[:conds.monotonic_improvement_quarters]
    if any(e is None for e in recent):
        return None
    # Reversed because rows are DESC — most recent first
    # Check: recent[0] > recent[1] > recent[2] > recent[3]
    improving = all(recent[i] > recent[i + 1] for i in range(len(recent) - 1))
    if not improving:
        return None

    # Condition 3: Most recent quarter EPS > 0
    if conds.latest_eps_positive and (recent[0] is None or recent[0] <= 0):
        return None

    # Condition 4: Revenue growing > 10% YoY
    latest_rev_growth = rows[0][2]
    if latest_rev_growth is None or latest_rev_growth < conds.min_revenue_growth_yoy * 100:
        return None

    # Condition 5: EPS block still active (< 2 of last 4 quarters positive)
    last_4 = eps_values[:4]
    positive_in_4 = sum(1 for e in last_4 if e is not None and e > 0)
    if positive_in_4 >= 2:
        return None  # Block already clearing — not a turnaround watch

    return TurnaroundCandidate(
        stock_id=stock_id,
        symbol=symbol,
        eps_trend=eps_values,
        revenue_growth_yoy=latest_rev_growth,
        suppressed=False,
        suppression_reason=None,
    )


def _check_suppression(db: Session, stock_id: int, config: TurnaroundWatchConfig) -> tuple[bool, str | None]:
    """Check if turnaround should be suppressed."""
    from momentum_edge.db.models import Stock

    stock = db.get(Stock, stock_id)
    if not stock:
        return False, None

    # Pledge > threshold
    if getattr(stock, "pledge_pct", None) and stock.pledge_pct > 0.20:
        return True, f"pledge_{stock.pledge_pct*100:.0f}pct"

    # SEBI fine active
    if getattr(stock, "sebi_fine_last_24m", False):
        return True, "sebi_fine_active"

    # Business pivots >= 3
    if getattr(stock, "business_pivot_count", 0) >= 3:
        return True, f"business_pivots_{stock.business_pivot_count}"

    # OCF negative 3+ of 4 quarters
    ocf_rows = db.execute(
        text("""
            SELECT ocf_cr FROM fundamentals
            WHERE stock_id = :sid AND ocf_cr IS NOT NULL
            ORDER BY quarter DESC LIMIT 4
        """),
        {"sid": stock_id},
    ).fetchall()

    if ocf_rows:
        neg_ocf = sum(1 for r in ocf_rows if r[0] is not None and r[0] < 0)
        if neg_ocf >= 3:
            return True, f"ocf_negative_{neg_ocf}of{len(ocf_rows)}"

    return False, None


def scan_turnarounds(
    db: Session,
    target_date: date,
    strategy=None,
) -> list[TurnaroundCandidate]:
    """
    Scan all active stocks for turnaround watch candidates.

    Returns list of candidates (including suppressed ones with reason).
    """
    config = strategy.turnaround_watch if strategy else None
    if config is None or not config.enabled:
        return []

    from momentum_edge.db.models import Stock

    stocks = db.query(Stock).filter(Stock.is_active.is_(True)).all()
    candidates = []

    for stock in stocks:
        candidate = _check_turnaround_conditions(
            db, stock.id, stock.symbol, target_date, config,
        )
        if candidate is None:
            continue

        # Check suppression
        suppressed, reason = _check_suppression(db, stock.id, config)
        candidate.suppressed = suppressed
        candidate.suppression_reason = reason

        candidates.append(candidate)

        if suppressed:
            logger.debug("{}: turnaround detected but SUPPRESSED ({})", stock.symbol, reason)
        else:
            logger.info("{}: TURNAROUND WATCH — EPS improving, revenue growing", stock.symbol)

    logger.info(
        "Turnaround scan: {} candidates ({} active, {} suppressed)",
        len(candidates),
        sum(1 for c in candidates if not c.suppressed),
        sum(1 for c in candidates if c.suppressed),
    )

    # Persist to turnaround_watch table
    _persist_turnarounds(db, candidates, target_date, strategy)

    return candidates


def _persist_turnarounds(
    db: Session,
    candidates: list[TurnaroundCandidate],
    target_date: date,
    strategy=None,
) -> None:
    """Persist turnaround candidates to the turnaround_watch table."""
    for c in candidates:
        try:
            db.execute(
                text("""
                    INSERT INTO turnaround_watch
                        (stock_id, detected_date, eps_trend, revenue_growth_yoy,
                         suppressed, suppression_reason, status)
                    VALUES (:sid, :d, :eps, :rev, :sup, :reason, 'watching')
                    ON CONFLICT (stock_id, detected_date) DO UPDATE SET
                        eps_trend = EXCLUDED.eps_trend,
                        revenue_growth_yoy = EXCLUDED.revenue_growth_yoy,
                        suppressed = EXCLUDED.suppressed,
                        suppression_reason = EXCLUDED.suppression_reason
                """),
                {
                    "sid": c.stock_id, "d": target_date,
                    "eps": str(c.eps_trend), "rev": c.revenue_growth_yoy,
                    "sup": c.suppressed, "reason": c.suppression_reason,
                },
            )
        except Exception:
            # Table may not exist yet
            db.rollback()
            break
