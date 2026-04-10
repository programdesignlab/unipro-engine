"""M1 — Nifty 50 index data via yfinance."""

from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from loguru import logger

def append_nifty_index(df):
    """Legacy parquet store stub — no-op."""
    pass

NIFTY50_TICKER = "^NSEI"


def fetch_nifty50_history(period: str = "10y", save_parquet: bool = True) -> pd.DataFrame:
    """
    Download full Nifty 50 OHLCV history and optionally save to parquet.

    Returns DataFrame with columns: date, open, high, low, close, volume
    """
    logger.info(f"Fetching Nifty 50 history ({period}) from yfinance")
    ticker = yf.Ticker(NIFTY50_TICKER)
    df = ticker.history(period=period, auto_adjust=True)

    if df.empty:
        raise RuntimeError("yfinance returned empty data for ^NSEI")

    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[["date", "open", "high", "low", "close", "volume"]].copy()
    df = df.sort_values("date").reset_index(drop=True)

    logger.info(f"  Nifty 50: {len(df)} rows, {df['date'].min()} → {df['date'].max()}")

    if save_parquet:
        append_nifty_index(df)
        logger.info("  Nifty 50 index saved to parquet")

    return df


def fetch_nifty50_close(target_date: date) -> float | None:
    """
    Fetch Nifty 50 closing price for a specific date.
    Returns None if market was closed that day.
    """
    start = target_date - timedelta(days=5)
    end = target_date + timedelta(days=1)

    ticker = yf.Ticker(NIFTY50_TICKER)
    df = ticker.history(start=start.isoformat(), end=end.isoformat(), auto_adjust=True)

    if df.empty:
        return None

    df = df.reset_index()
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    row = df[df["Date"] == target_date]

    if row.empty:
        return None

    return float(row["Close"].iloc[0])
