"""
Technical indicators calculator — populates the indicators table.

Computes per-stock per-date:
  - MA50, MA150, MA200 (simple moving averages)
  - RS score (relative strength vs Nifty 50 over 6 months)
  - ATR (14-day average true range)
  - 52-week high / low

Reads from parquet for bulk speed. Writes to PostgreSQL indicators table.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.data.parquet_store import read_prices, read_nifty_index


def _compute_indicators(prices: pd.DataFrame, nifty: pd.DataFrame, target_date: date) -> pd.DataFrame:
    """
    Compute indicators for all stocks for a single date.
    Returns DataFrame with columns: symbol, date, ma50, ma150, ma200, rs_score, atr, high_52w, low_52w
    """
    results = []
    nifty = nifty.sort_values("date")

    # Nifty 6-month return for RS calculation
    nifty_on_date = nifty[nifty["date"] <= target_date]
    if len(nifty_on_date) < 126:
        logger.warning("Not enough Nifty data for RS calculation")
        nifty_6m_return = 0.0
    else:
        nifty_close_now = nifty_on_date["close"].iloc[-1]
        nifty_close_6m = nifty_on_date["close"].iloc[-126]
        nifty_6m_return = (nifty_close_now / nifty_close_6m - 1) * 100

    for symbol, sdf in prices.groupby("symbol"):
        sdf = sdf.sort_values("date")
        sdf = sdf[sdf["date"] <= target_date]

        if len(sdf) < 200:
            continue

        close = sdf["close"].values
        high = sdf["high"].values
        low = sdf["low"].values

        # Moving averages
        ma50 = float(close[-50:].mean())
        ma150 = float(close[-150:].mean())
        ma200 = float(close[-200:].mean())

        # 52-week high/low (~252 trading days)
        lookback = min(252, len(close))
        high_52w = float(high[-lookback:].max())
        low_52w = float(low[-lookback:].min())

        # ATR (14-day)
        if len(sdf) >= 15:
            tr_data = sdf.tail(15)
            tr_high = tr_data["high"].values[1:]
            tr_low = tr_data["low"].values[1:]
            tr_prev_close = tr_data["close"].values[:-1]
            true_range = np.maximum(
                tr_high - tr_low,
                np.maximum(
                    np.abs(tr_high - tr_prev_close),
                    np.abs(tr_low - tr_prev_close),
                ),
            )
            atr = float(true_range.mean())
        else:
            atr = None

        # Relative strength vs Nifty (6-month)
        if len(sdf) >= 126:
            stock_close_now = close[-1]
            stock_close_6m = close[-126]
            stock_6m_return = (stock_close_now / stock_close_6m - 1) * 100
            rs_score = stock_6m_return - nifty_6m_return
        else:
            rs_score = None

        results.append({
            "symbol": symbol,
            "date": target_date,
            "ma50": round(ma50, 2),
            "ma150": round(ma150, 2),
            "ma200": round(ma200, 2),
            "rs_score": round(rs_score, 2) if rs_score is not None else None,
            "atr": round(atr, 2) if atr is not None else None,
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
        })

    return pd.DataFrame(results)


def compute_and_store_indicators(db: Session, target_date: date) -> int:
    """
    Compute technical indicators for all stocks and upsert into the indicators table.
    Returns count of rows written.
    """
    from momentum_edge.db.models import Stock

    prices = read_prices()
    nifty = read_nifty_index()

    if prices.empty:
        logger.warning("No price data in parquet — cannot compute indicators")
        return 0

    indicators_df = _compute_indicators(prices, nifty, target_date)
    if indicators_df.empty:
        logger.warning("No indicators computed")
        return 0

    # Map symbols to stock IDs
    stocks = {s.symbol: s.id for s in db.query(Stock).filter(Stock.is_active == True).all()}  # noqa: E712

    rows = []
    for _, row in indicators_df.iterrows():
        stock_id = stocks.get(row["symbol"])
        if not stock_id:
            continue
        rows.append({
            "stock_id": stock_id,
            "date": row["date"],
            "ma50": row["ma50"],
            "ma150": row["ma150"],
            "ma200": row["ma200"],
            "rs_score": row["rs_score"],
            "atr": row["atr"],
            "high_52w": row["high_52w"],
            "low_52w": row["low_52w"],
        })

    if not rows:
        return 0

    db.execute(
        text("""
            INSERT INTO indicators (stock_id, date, ma50, ma150, ma200, rs_score, atr, high_52w, low_52w)
            VALUES (:stock_id, :date, :ma50, :ma150, :ma200, :rs_score, :atr, :high_52w, :low_52w)
            ON CONFLICT (stock_id, date) DO UPDATE SET
                ma50 = EXCLUDED.ma50,
                ma150 = EXCLUDED.ma150,
                ma200 = EXCLUDED.ma200,
                rs_score = EXCLUDED.rs_score,
                atr = EXCLUDED.atr,
                high_52w = EXCLUDED.high_52w,
                low_52w = EXCLUDED.low_52w
        """),
        rows,
    )
    db.commit()

    logger.info(f"[Indicators] {len(rows)} stocks computed for {target_date}")
    return len(rows)
