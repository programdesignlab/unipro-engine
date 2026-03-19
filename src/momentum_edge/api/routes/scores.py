"""Score breakdown endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["scores"])


@router.get("/scores/{symbol}")
def get_scores(symbol: str, db: Session = Depends(get_db)):
    """Return the latest score breakdown for a given stock symbol."""
    row = db.execute(
        text(
            """
            SELECT sc.*, s.symbol, s.name
            FROM scores sc
            JOIN stocks s ON s.id = sc.stock_id
            WHERE s.symbol = :symbol
            ORDER BY sc.date DESC
            LIMIT 1
            """
        ),
        {"symbol": symbol.upper()},
    ).mappings().first()

    if not row:
        return {"detail": "No scores found for symbol"}

    return dict(row)
