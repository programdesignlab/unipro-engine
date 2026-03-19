"""
M6 — Institutional Accumulation Detection (max 11 pts).

v7 scoring:
  +5  OBV slope rising during base (passed in from breakout_patterns)
  +4  A/D ratio >= 0.60 (from indicators table)
  +2  Smart institutional flow positive (FII/DII/bulk deal logic)
"""

from datetime import date, timedelta

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

# Sectors where FII ownership is capped by regulation
_FII_CAPPED_SECTORS = frozenset({
    "Private Bank",
    "Insurance",
    "Defence",
    "Media",
    "Telecom",
})


def _check_bulk_deal_institutional_buy(
    db: Session, stock_id: int, target_date: date, lookback_days: int = 30
) -> bool:
    """Check bulk_deals table for a recent institutional buy."""
    row = db.execute(
        text("""
            SELECT 1 FROM bulk_deals
            WHERE stock_id = :stock_id
              AND date BETWEEN :start AND :end
              AND deal_type = 'buy'
            LIMIT 1
        """),
        {
            "stock_id": stock_id,
            "start": target_date - timedelta(days=lookback_days),
            "end": target_date,
        },
    ).fetchone()
    return row is not None


def _check_dii_net_positive(
    db: Session, target_date: date, lookback_days: int = 30
) -> bool:
    """Check fii_dii_data for recent net-positive DII flow (market aggregate)."""
    row = db.execute(
        text("""
            SELECT SUM(dii_net_cr) AS total_dii
            FROM fii_dii_data
            WHERE date BETWEEN :start AND :end
        """),
        {
            "start": target_date - timedelta(days=lookback_days),
            "end": target_date,
        },
    ).fetchone()
    return row is not None and row[0] is not None and row[0] > 0


def _check_fii_dii_combined_positive(
    db: Session, target_date: date, lookback_days: int = 30
) -> bool:
    """Check fii_dii_data for combined FII+DII net-positive flow (market aggregate)."""
    row = db.execute(
        text("""
            SELECT SUM(fii_net_cr + dii_net_cr) AS total_flow
            FROM fii_dii_data
            WHERE date BETWEEN :start AND :end
        """),
        {
            "start": target_date - timedelta(days=lookback_days),
            "end": target_date,
        },
    ).fetchone()
    return row is not None and row[0] is not None and row[0] > 0


def _smart_institutional_flow(
    db: Session, stock_id: int, symbol: str, target_date: date
) -> tuple[bool, str]:
    """
    Determine smart institutional flow based on promoter holding.

    Returns (is_positive, signal_type) where signal_type describes which
    data source was used: 'bulk_deal', 'dii_only', 'fii_dii_combined',
    or 'no_data'.
    """
    # Fetch promoter holding and sector info from stocks table
    row = db.execute(
        text("""
            SELECT promoter_holding_pct, sector, is_fii_breached
            FROM stocks
            WHERE id = :stock_id
        """),
        {"stock_id": stock_id},
    ).fetchone()

    if row is None:
        return False, "no_data"

    promoter_pct = row[0] if row[0] is not None else 0.0
    sector = row[1] or ""
    is_fii_breached = row[2] if row[2] is not None else False
    is_fii_capped_sector = sector in _FII_CAPPED_SECTORS

    # Route 1: High promoter / FII-restricted → use bulk deals
    if promoter_pct > 75 or is_fii_capped_sector or is_fii_breached:
        positive = _check_bulk_deal_institutional_buy(db, stock_id, target_date)
        return positive, "bulk_deal"

    # Route 2: Moderately high promoter → DII only
    if promoter_pct > 65:
        positive = _check_dii_net_positive(db, target_date)
        return positive, "dii_only"

    # Route 3: Lower promoter → FII + DII combined
    positive = _check_fii_dii_combined_positive(db, target_date)
    return positive, "fii_dii_combined"


def score_accumulation(
    db: Session,
    stock_id: int,
    symbol: str,
    target_date: date,
    obv_bonus: int = 0,
) -> dict:
    """
    Compute accumulation score for a single stock (max 11 pts).

    Parameters
    ----------
    obv_bonus : int
        +5 if OBV slope is rising during base (calculated in breakout_patterns
        and passed in by the pipeline).

    Returns
    -------
    dict with total, adl_bonus, obv_bonus, inst_bonus, inst_signal_type.
    """
    # --- 1. OBV slope bonus (0 or 5) ---
    obv_pts = min(5, max(0, obv_bonus))

    # --- 2. A/D ratio from indicators table (0 or 4) ---
    ad_row = db.execute(
        text("""
            SELECT adl_ratio FROM indicators
            WHERE stock_id = :stock_id AND date = :target_date
        """),
        {"stock_id": stock_id, "target_date": target_date},
    ).fetchone()

    ad_ratio = ad_row[0] if ad_row and ad_row[0] is not None else 0.0
    adl_bonus = 4 if ad_ratio >= 0.60 else 0

    # --- 3. Smart institutional flow (0 or 2) ---
    inst_positive, inst_signal_type = _smart_institutional_flow(
        db, stock_id, symbol, target_date
    )
    inst_bonus = 2 if inst_positive else 0

    total = obv_pts + adl_bonus + inst_bonus

    logger.debug(
        f"[M6] {symbol}: accum={total} "
        f"(OBV={obv_pts}, ADL={adl_bonus}, inst={inst_bonus} via {inst_signal_type})"
    )

    return {
        "symbol": symbol,
        "total": total,
        "obv_bonus": obv_pts,
        "adl_bonus": adl_bonus,
        "inst_bonus": inst_bonus,
        "inst_signal_type": inst_signal_type,
    }
