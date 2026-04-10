"""Turnaround watch API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["turnaround"])


@router.get("/turnaround-watch")
def get_turnaround_watch(
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """Return current turnaround watch candidates."""
    try:
        if active_only:
            rows = db.execute(
                text("""
                    SELECT tw.stock_id, s.symbol, s.sector, tw.detected_date,
                           tw.eps_trend, tw.revenue_growth_yoy,
                           tw.suppressed, tw.suppression_reason, tw.status
                    FROM turnaround_watch tw
                    JOIN stocks s ON s.id = tw.stock_id
                    WHERE tw.status = 'watching' AND tw.suppressed = false
                    ORDER BY tw.detected_date DESC
                """)
            ).mappings().all()
        else:
            rows = db.execute(
                text("""
                    SELECT tw.stock_id, s.symbol, s.sector, tw.detected_date,
                           tw.eps_trend, tw.revenue_growth_yoy,
                           tw.suppressed, tw.suppression_reason, tw.status
                    FROM turnaround_watch tw
                    JOIN stocks s ON s.id = tw.stock_id
                    ORDER BY tw.detected_date DESC
                    LIMIT 50
                """)
            ).mappings().all()

        return {
            "count": len(rows),
            "candidates": [dict(r) for r in rows],
        }
    except Exception:
        return {"count": 0, "candidates": [], "note": "turnaround_watch table not yet created"}
