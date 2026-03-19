"""Sector rotation endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["sectors"])


@router.get("/sectors")
def get_sectors(db: Session = Depends(get_db)):
    """Return sector rotation rankings (latest date)."""
    rows = db.execute(
        text(
            """
            SELECT *
            FROM sector_data
            ORDER BY date DESC, momentum_rank ASC
            """
        )
    ).mappings().all()

    if not rows:
        return []

    # Only return the latest date's data
    latest_date = rows[0]["date"]
    return [dict(r) for r in rows if r["date"] == latest_date]
