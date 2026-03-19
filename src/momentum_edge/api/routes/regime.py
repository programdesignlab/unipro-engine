"""Market regime endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["regime"])


@router.get("/regime")
def get_regime(db: Session = Depends(get_db)):
    """Return the current market regime."""
    # Get latest watchlist date's regime
    row = db.execute(
        text("""
            SELECT regime, date FROM watchlist
            ORDER BY date DESC, rank ASC
            LIMIT 1
        """)
    ).mappings().first()

    if not row:
        return {"regime": "unknown", "date": None, "detail": "No regime data available"}

    return {"regime": row["regime"], "date": str(row["date"])}
