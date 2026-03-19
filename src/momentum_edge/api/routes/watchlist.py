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
    """Return ranked watchlist for a given date."""
    if date:
        target_date = date_type.fromisoformat(date)
    else:
        # Get latest date
        row = db.execute(text("SELECT MAX(date) FROM watchlist")).scalar()
        if not row:
            return []
        target_date = row

    rows = db.execute(
        text("""
            SELECT w.rank, s.symbol, s.name, w.composite_score, w.pattern_type,
                   w.regime, w.stop_loss_level, w.sector_name, w.sector_rank
            FROM watchlist w
            JOIN stocks s ON s.id = w.stock_id
            WHERE w.date = :dt
            ORDER BY w.rank ASC
        """),
        {"dt": target_date},
    ).mappings().all()

    return [dict(r) for r in rows]
