"""Market regime endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["regime"])


@router.get("/regime")
def get_regime(db: Session = Depends(get_db)):
    """Return the current market regime."""
    row = db.execute(
        text("""
            SELECT regime, date FROM watchlist
            ORDER BY date DESC, rank ASC
            LIMIT 1
        """)
    ).mappings().first()

    if not row:
        return {"regime": "unknown", "date": None}

    return {"regime": row["regime"], "date": str(row["date"])}


@router.get("/regime/signals")
def get_regime_signals(db: Session = Depends(get_db)):
    """Return 6-signal regime breakdown with individual values.

    Computes signals from current indicator and price data.
    """
    from momentum_edge.data.parquet_store import read_nifty_index

    # Get latest indicator date
    latest_date = db.execute(
        text("SELECT MAX(date) FROM indicators")
    ).scalar()

    if not latest_date:
        return {"error": "No indicator data available"}

    # S1: Nifty close vs 200MA
    # S5: Extension from 200MA
    # S6: Nifty 12-1 month return
    nifty_df = read_nifty_index()
    nifty_close = None
    nifty_ma200 = None
    s1 = s2 = s5 = s6 = 0.0
    if not nifty_df.empty and len(nifty_df) >= 252:
        closes = nifty_df["close"].values
        nifty_close = float(closes[-1])
        nifty_ma200 = float(closes[-200:].mean())
        nifty_ma200_20d_ago = float(closes[-220:-20].mean()) if len(closes) >= 220 else nifty_ma200

        s1 = 1.0 if nifty_close > nifty_ma200 else 0.0
        s2 = 1.0 if nifty_ma200 > nifty_ma200_20d_ago else 0.0

        extension = abs(nifty_close / nifty_ma200 - 1) * 100 if nifty_ma200 > 0 else 0
        s5 = 1.0 if extension <= 15 else (0.5 if extension <= 25 else 0.0)

        mom_12_1 = (closes[-21] / closes[-252] - 1) if len(closes) >= 252 else 0
        s6 = 1.0 if mom_12_1 > 0 else 0.0

    # S3: Breadth (% stocks above 50MA)
    breadth_row = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE ma50 IS NOT NULL) as total,
                COUNT(*) FILTER (WHERE ma50 IS NOT NULL AND
                    (SELECT adj_close FROM eod_prices e
                     WHERE e.stock_id = i.stock_id AND e.date = i.date) > ma50
                ) as above_50ma
            FROM indicators i
            WHERE date = :dt
        """),
        {"dt": latest_date},
    ).mappings().first()

    breadth_pct = 0.0
    if breadth_row and breadth_row["total"] and breadth_row["total"] > 0:
        breadth_pct = breadth_row["above_50ma"] / breadth_row["total"] * 100
    s3 = 1.0 if breadth_pct > 60 else (0.5 if breadth_pct >= 40 else 0.0)

    # S4: New highs vs lows
    hl_row = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE pct_from_high >= -0.02) as new_highs,
                COUNT(*) FILTER (WHERE pct_from_high <= -0.48) as new_lows
            FROM indicators
            WHERE date = :dt AND pct_from_high IS NOT NULL
        """),
        {"dt": latest_date},
    ).mappings().first()

    new_highs = hl_row["new_highs"] if hl_row else 0
    new_lows = hl_row["new_lows"] if hl_row else 0
    if new_highs > 2 * max(new_lows, 1):
        s4 = 1.0
    elif new_lows > new_highs:
        s4 = 0.0
    else:
        s4 = 0.5

    score = s1 + s2 + s3 + s4 + s5 + s6

    # Crash indicator
    crash_warning = False
    if not nifty_df.empty and len(nifty_df) >= 504:
        closes = nifty_df["close"].values
        ret_2yr = float(closes[-1] / closes[-504] - 1)
        ret_1m = float(closes[-1] / closes[-21] - 1)
        crash_warning = bool(ret_2yr < -0.20 and ret_1m > 0.10)

    # Determine regime
    if crash_warning or score < 1.0:
        regime = "Full Bear"
    elif score < 2.5:
        regime = "Bear"
    elif score < 4.0:
        regime = "Weak"
    elif score < 5.0:
        regime = "Bull"
    else:
        regime = "Strong Bull"

    return {
        "date": str(latest_date),
        "regime": regime,
        "score": round(score, 1),
        "crash_warning": crash_warning,
        "signals": {
            "s1_nifty_above_200ma": {"value": s1, "label": "Nifty > 200MA", "nifty_close": nifty_close, "ma200": round(nifty_ma200, 2) if nifty_ma200 else None},
            "s2_ma200_slope_rising": {"value": s2, "label": "200MA slope rising"},
            "s3_breadth": {"value": s3, "label": f"Breadth ({breadth_pct:.0f}% above 50MA)", "breadth_pct": round(breadth_pct, 1)},
            "s4_highs_vs_lows": {"value": s4, "label": f"Highs vs Lows ({new_highs} vs {new_lows})", "new_highs": new_highs, "new_lows": new_lows},
            "s5_extension": {"value": s5, "label": "Nifty extension from 200MA"},
            "s6_index_momentum": {"value": s6, "label": "Nifty 12-1m return positive"},
        },
    }
