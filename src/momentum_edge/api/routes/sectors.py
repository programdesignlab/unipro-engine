"""Sector rotation endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["sectors"])


@router.get("/sectors")
def get_sectors(db: Session = Depends(get_db)):
    """Return sector data with stock counts and average momentum."""
    rows = db.execute(
        text("""
            SELECT sd.id, sd.sector_name, sd.parent_sector,
                   COUNT(s.id) as stock_count,
                   ROUND(AVG(i.scaled_score)::numeric, 2) as avg_momentum
            FROM sector_data sd
            LEFT JOIN stocks s ON s.sector_id = sd.id AND s.is_active = true
            LEFT JOIN indicators i ON i.stock_id = s.id
                AND i.date = (SELECT MAX(date) FROM indicators)
            GROUP BY sd.id, sd.sector_name, sd.parent_sector
            ORDER BY avg_momentum DESC NULLS LAST
        """)
    ).mappings().all()

    return [dict(r) for r in rows]
