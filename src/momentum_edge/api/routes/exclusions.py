"""Exclusion audit trail API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["exclusions"])


@router.get("/exclusions")
def get_exclusions(
    target_date: str | None = Query(None, description="Date YYYY-MM-DD (default: latest)"),
    symbol: str | None = Query(None, description="Filter by stock symbol"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Return recent exclusion log entries with optional filters."""
    try:
        conditions = []
        params: dict = {"limit": limit}

        if target_date:
            conditions.append("el.date = :d")
            params["d"] = target_date
        if symbol:
            conditions.append("s.symbol = :sym")
            params["sym"] = symbol.upper()

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        rows = db.execute(
            text(f"""
                SELECT el.date, s.symbol, el.block_name, el.reason,
                       el.data_missing, el.strategy_hash
                FROM exclusion_log el
                JOIN stocks s ON s.id = el.stock_id
                {where}
                ORDER BY el.date DESC, s.symbol
                LIMIT :limit
            """),
            params,
        ).mappings().all()

        return {
            "count": len(rows),
            "exclusions": [dict(r) for r in rows],
        }
    except Exception:
        return {"count": 0, "exclusions": [], "note": "exclusion_log table not yet created"}
