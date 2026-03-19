"""Stock detail composite endpoint."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["stock-detail"])


@router.get("/stock/{symbol}/detail")
def get_stock_detail(symbol: str, db: Session = Depends(get_db)):
    """Composite endpoint: stock metadata + latest price + indicators + scores + fundamentals + pattern."""
    sym = symbol.upper()

    # Stock metadata
    stock = db.execute(
        text("""
            SELECT id, symbol, name, sector, industry, market_cap, isin, exchange,
                   is_active, is_asm, is_esm, is_financial,
                   promoter_holding_pct, fii_holding_pct, dii_holding_pct,
                   is_fii_breached, is_fii_cautioned, free_float_pct, avg_daily_tv_cr,
                   screener_export_id
            FROM stocks WHERE symbol = :sym
        """),
        {"sym": sym},
    ).mappings().first()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {sym} not found")

    stock_id = stock["id"]

    # Latest price (OHLCV)
    price = db.execute(
        text("""
            SELECT date, open, high, low, close, adj_close, volume,
                   adj_factor, hit_upper_circuit, hit_lower_circuit
            FROM eod_prices
            WHERE stock_id = :sid
            ORDER BY date DESC
            LIMIT 1
        """),
        {"sid": stock_id},
    ).mappings().first()

    # Latest indicators
    indicator = db.execute(
        text("""
            SELECT date, ma50, ma150, ma200, ma200_slope,
                   rs_score, rs_rank, atr, high_52w, low_52w, pct_from_high,
                   mom_3m, mom_6m, mom_12_1,
                   raw_score, scaled_score, vol_scalar, mom_vol_20d, mom_quality,
                   obv, adl_ratio, vol_ratio_20, vol_ratio_50, delivery_trend
            FROM indicators
            WHERE stock_id = :sid
            ORDER BY date DESC
            LIMIT 1
        """),
        {"sid": stock_id},
    ).mappings().first()

    # Latest scores
    score = db.execute(
        text("""
            SELECT date, momentum_score, fundamental_score, sector_score,
                   technical_score, accumulation_score, breakout_score, composite_score
            FROM scores
            WHERE stock_id = :sid
            ORDER BY date DESC
            LIMIT 1
        """),
        {"sid": stock_id},
    ).mappings().first()

    # Latest fundamentals (last 4 quarters)
    fundamentals = db.execute(
        text("""
            SELECT quarter, eps, eps_yoy_growth, revenue, revenue_yoy_growth,
                   roe, net_margin, pe_ratio, debt_to_equity, is_financial,
                   reporting_date, expected_result_date
            FROM fundamentals
            WHERE stock_id = :sid
            ORDER BY quarter DESC
            LIMIT 4
        """),
        {"sid": stock_id},
    ).mappings().all()

    # Latest watchlist entry (pattern + stop loss)
    watchlist_entry = db.execute(
        text("""
            SELECT pattern_type, stop_loss_level, tier, entry_zone_low, entry_zone_high,
                   earnings_date, earnings_flag, vol_scalar, suggested_size_pct,
                   obv_bonus, adl_ratio as wl_adl_ratio, inst_flow_signal, inst_flow_positive
            FROM watchlist
            WHERE stock_id = :sid
            ORDER BY date DESC
            LIMIT 1
        """),
        {"sid": stock_id},
    ).mappings().first()

    return {
        "stock": dict(stock),
        "latest_price": dict(price) if price else None,
        "indicators": dict(indicator) if indicator else None,
        "scores": dict(score) if score else None,
        "fundamentals": [dict(f) for f in fundamentals],
        "watchlist": dict(watchlist_entry) if watchlist_entry else None,
    }
