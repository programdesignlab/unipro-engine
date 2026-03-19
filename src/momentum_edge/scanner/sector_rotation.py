"""
M3 — Sector Rotation Ranking.

Groups stocks by sector, calculates 6-month sector performance vs Nifty 50,
counts 52-week highs per sector, and produces a ranked list.
Top 3 sectors receive a priority multiplier in the composite score.
"""

from dataclasses import dataclass
from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class SectorRank:
    sector_name: str
    performance_6m: float  # % return over 6 months
    stocks_near_high: int  # count of stocks near 52w high
    sector_score: float    # combined score
    rank: int
    is_top3: bool


def rank_sectors(db: Session, target_date: date) -> list[SectorRank]:
    """
    Rank sectors by momentum strength. Returns sorted list of SectorRank.
    Requires indicators and eod_prices populated for target_date.
    """
    # Get sector performance: average 6m RS of stocks in each sector
    rows = db.execute(
        text("""
            SELECT
                COALESCE(s.sector, 'Unknown') AS sector_name,
                AVG(i.rs_score) AS avg_rs,
                COUNT(*) FILTER (WHERE e.close >= i.high_52w * 0.95) AS near_high_count,
                COUNT(*) AS stock_count
            FROM indicators i
            JOIN stocks s ON s.id = i.stock_id
            JOIN eod_prices e ON e.stock_id = i.stock_id AND e.date = i.date
            WHERE i.date = :target_date AND s.is_active = true
            GROUP BY COALESCE(s.sector, 'Unknown')
            HAVING COUNT(*) >= 2
            ORDER BY AVG(i.rs_score) DESC NULLS LAST
        """),
        {"target_date": target_date},
    ).fetchall()

    if not rows:
        logger.warning("[M3] No sector data available")
        return []

    results = []
    for i, row in enumerate(rows):
        sector_name = row[0]
        avg_rs = row[1] or 0.0
        near_high_count = row[2]
        stock_count = row[3]

        # Sector score: weighted combination of RS and % of stocks near highs
        pct_near_high = near_high_count / stock_count * 100 if stock_count > 0 else 0
        sector_score = avg_rs * 0.7 + pct_near_high * 0.3

        results.append(SectorRank(
            sector_name=sector_name,
            performance_6m=round(avg_rs, 2),
            stocks_near_high=near_high_count,
            sector_score=round(sector_score, 2),
            rank=i + 1,
            is_top3=(i < 3),
        ))

    # Log top sectors
    for sr in results[:3]:
        logger.info(f"[M3] Top sector #{sr.rank}: {sr.sector_name} (RS={sr.performance_6m}, score={sr.sector_score})")

    return results


def get_sector_score(sector_ranks: list[SectorRank], sector_name: str) -> float:
    """
    Get the sector score (max 20 pts) for a stock's sector.
    Top 3 sectors get 20/15/12 pts; others get scaled down.
    """
    if not sector_ranks or not sector_name:
        return 0.0

    for sr in sector_ranks:
        if sr.sector_name == sector_name:
            if sr.rank == 1:
                return 20.0
            elif sr.rank == 2:
                return 15.0
            elif sr.rank == 3:
                return 12.0
            else:
                # Linear decay from 10 to 0 for remaining sectors
                total = len(sector_ranks)
                remaining = total - 3
                if remaining <= 0:
                    return 5.0
                position = sr.rank - 3  # 1-indexed position after top 3
                return max(0.0, round(10.0 * (1 - position / remaining), 1))

    return 0.0
