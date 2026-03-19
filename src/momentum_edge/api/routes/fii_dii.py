"""FII/DII flow endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["fii-dii"])


@router.get("/fii-dii")
def get_fii_dii(
    days: int = Query(30, description="Number of days of history"),
    db: Session = Depends(get_db),
):
    """Return daily FII/DII aggregate flows."""
    rows = db.execute(
        text("""
            SELECT date, fii_buy_cr, fii_sell_cr, fii_net_cr,
                   dii_buy_cr, dii_sell_cr, dii_net_cr
            FROM fii_dii_data
            ORDER BY date DESC
            LIMIT :days
        """),
        {"days": days},
    ).mappings().all()

    return [dict(r) for r in rows]
