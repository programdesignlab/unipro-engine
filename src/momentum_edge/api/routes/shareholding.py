"""Shareholding pattern endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["shareholding"])


@router.get("/shareholding/{symbol}")
def get_shareholding(symbol: str, db: Session = Depends(get_db)):
    """Return quarterly shareholding pattern for a stock."""
    sym = symbol.upper()

    stock = db.execute(
        text("SELECT id FROM stocks WHERE symbol = :sym"),
        {"sym": sym},
    ).scalar()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {sym} not found")

    rows = db.execute(
        text("""
            SELECT quarter_end_date, promoter_pct, fii_pct, dii_pct, public_pct
            FROM shareholding_pattern
            WHERE stock_id = :sid
            ORDER BY quarter_end_date ASC
        """),
        {"sid": stock},
    ).mappings().all()

    return [dict(r) for r in rows]
