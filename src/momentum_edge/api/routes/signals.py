"""Signal history endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["signals"])


@router.get("/signals/{symbol}")
def get_signals(
    symbol: str,
    limit: int = Query(20, description="Max signals to return"),
    db: Session = Depends(get_db),
):
    """Return signal history for a stock with lifecycle status."""
    sym = symbol.upper()

    # Get stock_id
    stock = db.execute(
        text("SELECT id FROM stocks WHERE symbol = :sym"),
        {"sym": sym},
    ).scalar()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {sym} not found")

    rows = db.execute(
        text("""
            SELECT signal_date, pattern_type, status, tier,
                   pivot_price, stop_loss, entry_zone_low, entry_zone_high,
                   volume_ratio, obv_slope, obv_bonus, obv_divergence,
                   adl_ratio, inst_flow_signal, inst_flow_positive,
                   base_length_days, base_depth_pct,
                   regime, crash_warning,
                   earnings_date, days_to_earnings, earnings_flag,
                   composite_score, vol_scalar, fundamental_bonus,
                   confirmed_date, failed_date
            FROM signals
            WHERE stock_id = :sid
            ORDER BY signal_date DESC
            LIMIT :lim
        """),
        {"sid": stock, "lim": limit},
    ).mappings().all()

    return [dict(r) for r in rows]
