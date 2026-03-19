"""Stock universe endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["stocks"])


@router.get("/stocks")
def get_stocks(
    active: bool | None = Query(None, description="Filter to active stocks only"),
    db: Session = Depends(get_db),
):
    """Return the stock universe with basic info."""
    if active:
        rows = db.execute(
            text("SELECT * FROM stocks WHERE is_active = true ORDER BY symbol ASC")
        ).mappings().all()
    else:
        rows = db.execute(
            text("SELECT * FROM stocks ORDER BY symbol ASC")
        ).mappings().all()

    return [dict(r) for r in rows]
