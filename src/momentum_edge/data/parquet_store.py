"""
Parquet archive layer — historical data store alongside PostgreSQL.

Layout:
  data/parquet/
    price_data.parquet       — OHLCV per symbol per date
    delivery_data.parquet    — NSE delivery qty/% per symbol per date
    nifty50_index.parquet    — Nifty 50 index OHLCV

Each file is a flat parquet with snappy compression.
Deduplication key: (symbol, date) for prices/delivery, (date,) for index.
"""

from pathlib import Path

import pandas as pd
from loguru import logger

PARQUET_DIR = Path("data/parquet")
PRICE_FILE    = PARQUET_DIR / "price_data.parquet"
DELIVERY_FILE = PARQUET_DIR / "delivery_data.parquet"
NIFTY_FILE    = PARQUET_DIR / "nifty50_index.parquet"


def _ensure_dir() -> None:
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)


def _read(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


def _write(df: pd.DataFrame, path: Path) -> None:
    df.to_parquet(path, index=False, compression="snappy")


# ── Price data ────────────────────────────────────────────────────────────────

def append_prices(df: pd.DataFrame) -> None:
    """
    Append/upsert OHLCV rows to price_data.parquet.

    df must have columns: symbol, date, open, high, low, close, volume
    Deduplicates on (symbol, date) — newer rows win.
    """
    if df.empty:
        return

    _ensure_dir()
    existing = _read(PRICE_FILE)

    combined = pd.concat([existing, df], ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"]).dt.date
    combined = (
        combined
        .sort_values("date")
        .drop_duplicates(subset=["symbol", "date"], keep="last")
        .reset_index(drop=True)
    )

    _write(combined, PRICE_FILE)
    logger.debug(f"Parquet price_data: {len(combined)} total rows after append")


def read_prices(symbols: list[str] | None = None) -> pd.DataFrame:
    """Read all price data, optionally filtered to a list of symbols."""
    df = _read(PRICE_FILE)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"]).dt.date
    if symbols:
        df = df[df["symbol"].isin(symbols)]
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


# ── Nifty 50 index ────────────────────────────────────────────────────────────

def append_nifty_index(df: pd.DataFrame) -> None:
    """
    Append/upsert Nifty 50 index rows to nifty50_index.parquet.

    df must have columns: date, open, high, low, close, volume
    Deduplicates on date — newer rows win.
    """
    if df.empty:
        return

    _ensure_dir()
    existing = _read(NIFTY_FILE)

    combined = pd.concat([existing, df], ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"]).dt.date
    combined = (
        combined
        .sort_values("date")
        .drop_duplicates(subset=["date"], keep="last")
        .reset_index(drop=True)
    )

    _write(combined, NIFTY_FILE)
    logger.debug(f"Parquet nifty50_index: {len(combined)} total rows after append")


def read_nifty_index() -> pd.DataFrame:
    """Read full Nifty 50 index history from parquet."""
    df = _read(NIFTY_FILE)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.sort_values("date").reset_index(drop=True) if not df.empty else df


# ── Delivery data ─────────────────────────────────────────────────────────────

def append_delivery(df: pd.DataFrame) -> None:
    """
    Append/upsert delivery rows to delivery_data.parquet.

    df must have columns: symbol, date, delivery_qty, delivery_pct, traded_qty
    Deduplicates on (symbol, date) — newer rows win.
    """
    if df.empty:
        return

    _ensure_dir()
    existing = _read(DELIVERY_FILE)

    combined = pd.concat([existing, df], ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"]).dt.date
    combined = (
        combined
        .sort_values("date")
        .drop_duplicates(subset=["symbol", "date"], keep="last")
        .reset_index(drop=True)
    )

    _write(combined, DELIVERY_FILE)
    logger.debug(f"Parquet delivery_data: {len(combined)} total rows after append")


def read_delivery(symbols: list[str] | None = None) -> pd.DataFrame:
    """Read delivery data, optionally filtered to a list of symbols."""
    df = _read(DELIVERY_FILE)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"]).dt.date
    if symbols:
        df = df[df["symbol"].isin(symbols)]
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)
