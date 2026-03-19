"""Watchlist endpoints."""
from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["watchlist"])


@router.get("/watchlist")
def get_watchlist(
    date: str | None = Query(None, description="Date YYYY-MM-DD; defaults to latest"),
    db: Session = Depends(get_db),
):
    """Return ranked watchlist with full score breakdown and signal details."""
    if date:
        target_date = date_type.fromisoformat(date)
    else:
        row = db.execute(text("SELECT MAX(date) FROM watchlist")).scalar()
        if not row:
            return []
        target_date = row

    rows = db.execute(
        text("""
            SELECT
                w.rank, s.symbol, s.name, s.sector, s.industry,
                w.composite_score, w.pattern_type, w.regime,
                w.stop_loss_level, w.sector_name, w.sector_rank,
                w.tier, w.entry_zone_low, w.entry_zone_high,
                w.earnings_date, w.earnings_flag, w.vol_scalar,
                w.suggested_size_pct,
                w.inst_flow_signal, w.inst_flow_positive,
                w.obv_bonus, w.adl_ratio, w.delivery_trend,
                w.momentum_score, w.fundamental_bonus,
                sc.momentum_score  AS scaled_score,
                sc.fundamental_score,
                sc.sector_score,
                sc.technical_score,
                sc.accumulation_score,
                sc.breakout_score
            FROM watchlist w
            JOIN stocks s ON s.id = w.stock_id
            LEFT JOIN scores sc ON sc.stock_id = w.stock_id AND sc.date = w.date
            WHERE w.date = :dt
            ORDER BY w.rank ASC
        """),
        {"dt": target_date},
    ).mappings().all()

    return [dict(r) for r in rows]
