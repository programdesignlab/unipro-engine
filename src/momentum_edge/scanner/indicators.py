"""
Technical indicators calculator v7 — populates the indicators table.

Computes per-stock per-date (all on adj_close):
  - MA50, MA150, MA200, MA200 slope
  - Momentum returns: 3m, 6m, 12-1m
  - Volatility scalar (Barroso & Santa-Clara 2015)
  - Momentum quality (weekly positive weeks ratio)
  - RS score & percentile rank vs Nifty 50
  - OBV, A/D ratio (20-day)
  - Volume ratios (20d, 50d)
  - ATR (14-day)
  - 52-week high/low, pct_from_high
  - Delivery trend (display only, not scored)
  - raw_score / scaled_score (momentum composite)

Reads price data from eod_prices table (not parquet).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.models import DeliveryData, EODPrice, Stock


# ---------------------------------------------------------------------------
# Per-stock indicator computation
# ---------------------------------------------------------------------------


def _compute_stock_indicators(
    prices: pd.DataFrame,
    nifty_6m_return: float,
    target_date: date,
    delivery_df: pd.DataFrame | None = None,
) -> dict[str, Any] | None:
    """
    Compute all v7 indicators for a single stock.

    Parameters
    ----------
    prices : DataFrame
        Columns: [date, adj_close, close, high, low, volume], sorted by date,
        filtered to rows <= target_date.
    nifty_6m_return : float
        Nifty 50 6-month return in percentage points.
    target_date : date
        The date we are computing indicators for.
    delivery_df : DataFrame | None
        Columns: [date, delivery_pct] for this stock, sorted by date.

    Returns
    -------
    dict with all indicator values, or None if insufficient data.
    """
    if len(prices) < 200:
        return None

    p = prices["adj_close"]
    v = prices["volume"].astype(float)

    current_price = p.iloc[-1]

    # --- Moving averages ---
    ma50 = p.rolling(50).mean().iloc[-1]
    ma150 = p.rolling(150).mean().iloc[-1]
    ma200 = p.rolling(200).mean().iloc[-1]

    # MA200 slope: current MA200 minus MA200 from 20 trading days ago
    ma200_series = p.rolling(200).mean()
    if len(ma200_series) >= 21:
        ma200_slope = ma200_series.iloc[-1] - ma200_series.iloc[-21]
    else:
        ma200_slope = 0.0

    # --- ATR (14-day) ---
    # Use high/low if available, otherwise approximate from adj_close
    if "high" in prices.columns and "low" in prices.columns and len(prices) >= 15:
        tr_slice = prices.tail(15)
        tr_high = tr_slice["high"].values[1:]
        tr_low = tr_slice["low"].values[1:]
        tr_prev_close = tr_slice["adj_close"].values[:-1]
        true_range = np.maximum(
            tr_high - tr_low,
            np.maximum(
                np.abs(tr_high - tr_prev_close),
                np.abs(tr_low - tr_prev_close),
            ),
        )
        atr = float(true_range.mean())
    elif len(p) >= 15:
        # Approximate ATR from adj_close daily range
        daily_abs = p.diff().abs()
        atr = float(daily_abs.tail(14).mean())
    else:
        atr = None

    # --- Momentum returns ---
    mom_3m = (current_price / p.iloc[-63] - 1) if len(p) >= 63 else None
    mom_6m = (current_price / p.iloc[-126] - 1) if len(p) >= 126 else None
    # 12-month excluding last month (skip last 21 trading days)
    mom_12_1 = (p.iloc[-21] / p.iloc[-252] - 1) if len(p) >= 252 else None

    # --- Volatility scaling (Barroso & Santa-Clara 2015) ---
    daily_ret = p.pct_change()
    mom_vol_20d = float(daily_ret.rolling(20).std().iloc[-1])
    vol_annualised = mom_vol_20d * (252**0.5)
    if vol_annualised > 0:
        vol_scalar = min(0.20 / vol_annualised, 2.0)
    else:
        vol_scalar = 1.0

    # --- Momentum quality (smooth uptrend filter) ---
    # Resample to weekly using DatetimeIndex
    p_ts = p.copy()
    p_ts.index = pd.to_datetime(prices["date"].values)
    weekly = p_ts.resample("W").last().dropna().pct_change()
    if len(weekly) >= 26:
        mom_quality = float((weekly.tail(26) > 0).sum() / 26)
    else:
        mom_quality = float((weekly > 0).sum() / len(weekly)) if len(weekly) > 0 else 0.0

    # --- RS score vs Nifty 50 (6-month relative strength) ---
    if len(p) >= 126:
        stock_6m_return = (current_price / p.iloc[-126] - 1) * 100
        rs_score = stock_6m_return - nifty_6m_return
    else:
        rs_score = None

    # --- OBV (On-Balance Volume) ---
    price_diff = p.diff()
    sign = price_diff.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = float((sign * v).cumsum().iloc[-1])

    # --- A/D ratio (20-day accumulation/distribution) ---
    last20 = prices.tail(20)
    adj_close_20 = last20["adj_close"]
    vol_20 = last20["volume"]
    up_mask = adj_close_20 > adj_close_20.shift(1)
    dn_mask = adj_close_20 < adj_close_20.shift(1)
    up_vol = float(vol_20[up_mask].sum())
    dn_vol = float(vol_20[dn_mask].sum())
    adl_ratio = up_vol / (up_vol + dn_vol) if (up_vol + dn_vol) > 0 else 0.5

    # --- Volume ratios ---
    vol_ma_20 = v.rolling(20).mean().iloc[-1]
    vol_ma_50 = v.rolling(50).mean().iloc[-1]
    vol_ratio_20 = float(v.iloc[-1] / vol_ma_20) if vol_ma_20 > 0 else None
    vol_ratio_50 = float(v.iloc[-1] / vol_ma_50) if vol_ma_50 > 0 else None

    # --- 52-week metrics ---
    lookback_252 = p.tail(252)
    high_52w = float(lookback_252.max())
    low_52w = float(lookback_252.min())
    pct_from_high = (current_price / high_52w) - 1

    # --- Delivery trend (display only, NOT scored) ---
    delivery_trend = None
    if delivery_df is not None and len(delivery_df) >= 20:
        recent_10 = delivery_df["delivery_pct"].tail(10).mean()
        prev_10 = delivery_df["delivery_pct"].iloc[-20:-10].mean()
        if prev_10 > 0:
            delivery_trend = (recent_10 / prev_10) - 1  # positive = improving
        else:
            delivery_trend = 0.0

    return {
        "ma50": round(ma50, 2),
        "ma150": round(ma150, 2),
        "ma200": round(ma200, 2),
        "ma200_slope": round(ma200_slope, 4),
        "atr": round(atr, 2) if atr is not None else None,
        "mom_3m": round(mom_3m, 4) if mom_3m is not None else None,
        "mom_6m": round(mom_6m, 4) if mom_6m is not None else None,
        "mom_12_1": round(mom_12_1, 4) if mom_12_1 is not None else None,
        "rs_score": round(rs_score, 2) if rs_score is not None else None,
        "vol_scalar": round(vol_scalar, 4),
        "mom_vol_20d": round(mom_vol_20d, 6),
        "mom_quality": round(mom_quality, 4),
        "obv": round(obv, 0),
        "adl_ratio": round(adl_ratio, 4),
        "vol_ratio_20": round(vol_ratio_20, 4) if vol_ratio_20 is not None else None,
        "vol_ratio_50": round(vol_ratio_50, 4) if vol_ratio_50 is not None else None,
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "pct_from_high": round(pct_from_high, 4),
        "delivery_trend": round(delivery_trend, 4) if delivery_trend is not None else None,
    }


# ---------------------------------------------------------------------------
# Cross-sectional ranking & scoring
# ---------------------------------------------------------------------------

# Momentum factor weights for raw_score (percentile-ranked inputs)
_FACTOR_WEIGHTS = {
    "mom_3m": 0.20,
    "mom_6m": 0.30,
    "mom_12_1": 0.25,
    "mom_quality": 0.15,
    "rs_score": 0.10,
}


def _compute_ranks_and_scores(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Given a list of per-stock indicator dicts, compute cross-sectional:
      - rs_rank: percentile rank of rs_score (1 = best / highest RS)
      - raw_score: weighted combo of percentile-ranked momentum factors
      - scaled_score: raw_score * vol_scalar
    """
    if not results:
        return results

    df = pd.DataFrame(results)

    # --- RS rank (percentile, 1 = best) ---
    valid_rs = df["rs_score"].notna()
    if valid_rs.sum() > 0:
        # Percentile rank: higher rs_score → lower rank number (1 = best)
        df.loc[valid_rs, "rs_rank"] = (
            df.loc[valid_rs, "rs_score"]
            .rank(ascending=False, method="min")
            .astype(int)
        )
    else:
        df["rs_rank"] = None

    # --- Percentile ranks for momentum factors ---
    pct_ranks = {}
    for factor in _FACTOR_WEIGHTS:
        col = df[factor]
        valid = col.notna()
        if valid.sum() > 1:
            # scipy percentileofscore gives 0-100; we convert to 0-1
            ranked = col[valid].rank(pct=True)
            pct_ranks[factor] = ranked
        else:
            pct_ranks[factor] = pd.Series(np.nan, index=df.index)

    # --- raw_score: weighted sum of percentile ranks (0–1 scale) ---
    raw_scores = pd.Series(0.0, index=df.index)
    total_weight = pd.Series(0.0, index=df.index)
    for factor, weight in _FACTOR_WEIGHTS.items():
        pct = pct_ranks[factor].reindex(df.index)
        valid = pct.notna()
        raw_scores[valid] += pct[valid] * weight
        total_weight[valid] += weight

    # Normalise by actual weight used (handle missing factors gracefully)
    has_any = total_weight > 0
    df.loc[has_any, "raw_score"] = (raw_scores[has_any] / total_weight[has_any] * 100).round(2)
    df.loc[~has_any, "raw_score"] = None

    # --- scaled_score = raw_score * vol_scalar ---
    df["scaled_score"] = (df["raw_score"] * df["vol_scalar"]).round(2)
    df.loc[df["raw_score"].isna(), "scaled_score"] = None

    # Convert back to list of dicts
    return df.to_dict("records")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def compute_and_store_indicators(db: Session, target_date: date) -> int:
    """
    Compute all v7 technical indicators for every active stock and upsert into
    the indicators table.

    Steps:
      1. Load all active stocks from DB.
      2. Load Nifty 50 index data for RS calculation.
      3. For each stock, load price history from eod_prices (adj_close, volume).
      4. Compute per-stock indicators.
      5. Cross-sectional: compute rs_rank, raw_score, scaled_score.
      6. Bulk upsert into indicators table.

    Returns count of rows written.
    """
    # --- 1. Active stocks ---
    active_stocks = db.query(Stock).filter(Stock.is_active.is_(True)).all()
    stock_map = {s.id: s.symbol for s in active_stocks}
    if not stock_map:
        logger.warning("No active stocks found in DB")
        return 0

    stock_ids = list(stock_map.keys())

    # --- 2. Nifty 50 index for RS baseline ---
    # Try reading from eod_prices via a stock named "NIFTY 50" or "^NSEI",
    # otherwise fall back to parquet.
    nifty_6m_return = _load_nifty_6m_return(db, target_date)

    # --- 3 & 4. Load prices + compute per-stock ---
    # Batch-load all prices in one query for efficiency
    price_rows = (
        db.query(
            EODPrice.stock_id,
            EODPrice.date,
            EODPrice.adj_close,
            EODPrice.close,
            EODPrice.high,
            EODPrice.low,
            EODPrice.volume,
        )
        .filter(
            EODPrice.stock_id.in_(stock_ids),
            EODPrice.date <= target_date,
            EODPrice.adj_close.isnot(None),
        )
        .order_by(EODPrice.stock_id, EODPrice.date)
        .all()
    )

    if not price_rows:
        logger.warning("No price data found in eod_prices — cannot compute indicators")
        return 0

    prices_df = pd.DataFrame(
        price_rows,
        columns=["stock_id", "date", "adj_close", "close", "high", "low", "volume"],
    )

    # --- Batch-load delivery data ---
    delivery_rows = (
        db.query(
            DeliveryData.stock_id,
            DeliveryData.date,
            DeliveryData.delivery_pct,
        )
        .filter(
            DeliveryData.stock_id.in_(stock_ids),
            DeliveryData.date <= target_date,
        )
        .order_by(DeliveryData.stock_id, DeliveryData.date)
        .all()
    )
    delivery_df_all = pd.DataFrame(
        delivery_rows, columns=["stock_id", "date", "delivery_pct"]
    ) if delivery_rows else pd.DataFrame(columns=["stock_id", "date", "delivery_pct"])

    # --- Compute per-stock ---
    results: list[dict[str, Any]] = []
    skipped = 0

    for sid, group in prices_df.groupby("stock_id"):
        group = group.sort_values("date").reset_index(drop=True)

        # Delivery data for this stock
        del_df = delivery_df_all[delivery_df_all["stock_id"] == sid].sort_values("date").reset_index(drop=True)
        del_input = del_df if not del_df.empty else None

        indicators = _compute_stock_indicators(group, nifty_6m_return, target_date, del_input)
        if indicators is None:
            skipped += 1
            continue

        indicators["stock_id"] = sid
        indicators["date"] = target_date
        results.append(indicators)

    if skipped:
        logger.debug(f"[Indicators] Skipped {skipped} stocks with < 200 days of data")

    if not results:
        logger.warning("No indicators computed (all stocks had insufficient history)")
        return 0

    # --- 5. Cross-sectional ranks & scores ---
    results = _compute_ranks_and_scores(results)

    # --- 6. Bulk upsert ---
    _upsert_indicators(db, results)

    logger.info(f"[Indicators] {len(results)} stocks computed for {target_date}")
    return len(results)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_nifty_6m_return(db: Session, target_date: date) -> float:
    """
    Load Nifty 50 6-month return for RS calculation.
    Tries eod_prices (stock symbol containing 'NIFTY') first, then parquet fallback.
    """
    # Try DB: look for a stock entry for the index
    nifty_stock = (
        db.query(Stock)
        .filter(Stock.symbol.in_(["NIFTY 50", "^NSEI", "NIFTY50"]))
        .first()
    )

    if nifty_stock:
        nifty_prices = (
            db.query(EODPrice.date, EODPrice.close)
            .filter(EODPrice.stock_id == nifty_stock.id, EODPrice.date <= target_date)
            .order_by(EODPrice.date)
            .all()
        )
        if len(nifty_prices) >= 126:
            nifty_close_now = nifty_prices[-1][1]
            nifty_close_6m = nifty_prices[-126][1]
            return (nifty_close_now / nifty_close_6m - 1) * 100

    # Fallback: try parquet
    try:
        from momentum_edge.data.parquet_store import read_nifty_index

        nifty = read_nifty_index()
        if not nifty.empty:
            nifty = nifty.sort_values("date")
            nifty = nifty[nifty["date"] <= pd.Timestamp(target_date)]
            if len(nifty) >= 126:
                close_now = nifty["close"].iloc[-1]
                close_6m = nifty["close"].iloc[-126]
                return (close_now / close_6m - 1) * 100
    except Exception:
        logger.debug("Parquet Nifty data unavailable; RS score will use 0 baseline")

    logger.warning("No Nifty 50 data found for RS calculation — using 0% baseline")
    return 0.0


def _upsert_indicators(db: Session, rows: list[dict[str, Any]]) -> None:
    """Bulk upsert indicator rows using ON CONFLICT."""
    if not rows:
        return

    # Clean NaN/inf values for PostgreSQL compatibility
    clean_rows = []
    for row in rows:
        clean = {}
        for k, v in row.items():
            if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                clean[k] = None
            else:
                clean[k] = v
        clean_rows.append(clean)

    upsert_sql = text("""
        INSERT INTO indicators (
            stock_id, date,
            ma50, ma150, ma200, ma200_slope,
            rs_score, rs_rank,
            atr, high_52w, low_52w, pct_from_high,
            mom_3m, mom_6m, mom_12_1,
            raw_score, scaled_score,
            vol_scalar, mom_vol_20d, mom_quality,
            obv, adl_ratio,
            vol_ratio_20, vol_ratio_50,
            delivery_trend
        ) VALUES (
            :stock_id, :date,
            :ma50, :ma150, :ma200, :ma200_slope,
            :rs_score, :rs_rank,
            :atr, :high_52w, :low_52w, :pct_from_high,
            :mom_3m, :mom_6m, :mom_12_1,
            :raw_score, :scaled_score,
            :vol_scalar, :mom_vol_20d, :mom_quality,
            :obv, :adl_ratio,
            :vol_ratio_20, :vol_ratio_50,
            :delivery_trend
        )
        ON CONFLICT (stock_id, date) DO UPDATE SET
            ma50 = EXCLUDED.ma50,
            ma150 = EXCLUDED.ma150,
            ma200 = EXCLUDED.ma200,
            ma200_slope = EXCLUDED.ma200_slope,
            rs_score = EXCLUDED.rs_score,
            rs_rank = EXCLUDED.rs_rank,
            atr = EXCLUDED.atr,
            high_52w = EXCLUDED.high_52w,
            low_52w = EXCLUDED.low_52w,
            pct_from_high = EXCLUDED.pct_from_high,
            mom_3m = EXCLUDED.mom_3m,
            mom_6m = EXCLUDED.mom_6m,
            mom_12_1 = EXCLUDED.mom_12_1,
            raw_score = EXCLUDED.raw_score,
            scaled_score = EXCLUDED.scaled_score,
            vol_scalar = EXCLUDED.vol_scalar,
            mom_vol_20d = EXCLUDED.mom_vol_20d,
            mom_quality = EXCLUDED.mom_quality,
            obv = EXCLUDED.obv,
            adl_ratio = EXCLUDED.adl_ratio,
            vol_ratio_20 = EXCLUDED.vol_ratio_20,
            vol_ratio_50 = EXCLUDED.vol_ratio_50,
            delivery_trend = EXCLUDED.delivery_trend
    """)

    db.execute(upsert_sql, clean_rows)
    db.commit()
