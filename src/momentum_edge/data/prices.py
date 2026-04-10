"""
M1 — OHLCV price data ingestion.

Primary source: yfinance (10yr history, auto-adjusted for splits)
Fallback: jugaad-data (for symbols missing on yfinance, e.g. TATAMOTORS)
Daily: NSE bulk bhav CSV (1 HTTP call for all stocks)

Handles both:
  - bootstrap_prices(): bulk historical load (10 years)
  - ingest_daily_prices(): single-day incremental update
"""

from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.models import Stock
def append_prices(df):
    """Legacy parquet store stub — no-op."""
    pass


def _yf_symbol(nse_symbol: str) -> str:
    return f"{nse_symbol}.NS"


def _upsert_prices(db: Session, rows: list[dict]) -> int:
    """Bulk insert price rows, ignoring conflicts on (stock_id, date)."""
    if not rows:
        return 0
    db.execute(
        text("""
            INSERT INTO eod_prices (stock_id, date, open, high, low, close, volume)
            VALUES (:stock_id, :date, :open, :high, :low, :close, :volume)
            ON CONFLICT (stock_id, date) DO UPDATE SET
                open   = EXCLUDED.open,
                high   = EXCLUDED.high,
                low    = EXCLUDED.low,
                close  = EXCLUDED.close,
                volume = EXCLUDED.volume
        """),
        rows,
    )
    db.commit()
    return len(rows)


def _fetch_jugaad_prices(symbol: str, from_date: date, to_date: date) -> pd.DataFrame:
    """
    Fetch OHLCV for a single symbol via jugaad-data (NSE scraper).
    Used as fallback when yfinance doesn't have the symbol.
    Returns DataFrame with columns: Date, Open, High, Low, Close, Volume
    """
    try:
        import concurrent.futures
        from jugaad_data.nse import stock_df as nse_stock_df

        def _do_fetch():
            return nse_stock_df(
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                series="EQ",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_fetch)
            raw = future.result(timeout=60)

        if raw is None or raw.empty:
            return pd.DataFrame()

        df = raw[["DATE", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]].copy()
        df.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
        df["Date"] = pd.to_datetime(df["Date"]).dt.date
        return df.reset_index(drop=True)

    except Exception as e:
        logger.warning(f"  {symbol}: jugaad-data fetch failed — {e}")
        return pd.DataFrame()


def bootstrap_prices(
    db: Session,
    symbols: list[str] | None = None,
    period: str = "10y",
    skip_existing: bool = True,
) -> None:
    """
    Download full historical OHLCV for all stocks and load into eod_prices.
    Intended for one-time bootstrap only.

    Uses yfinance as primary source. Falls back to jugaad-data for symbols
    that yfinance can't find (e.g. TATAMOTORS).

    Parameters
    ----------
    skip_existing : bool
        If True, skip stocks that already have recent price data (within 30 days).
    """
    stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
    if symbols:
        stocks = [s for s in stocks if s.symbol in symbols]

    if skip_existing:
        cutoff = date.today() - timedelta(days=30)
        done = {r[0] for r in db.execute(
            text("SELECT stock_id FROM eod_prices WHERE date >= :cutoff GROUP BY stock_id"),
            {"cutoff": cutoff}
        ).fetchall()}
        skipped = [s for s in stocks if s.id in done]
        stocks = [s for s in stocks if s.id not in done]
        if skipped:
            logger.info(f"Skipping {len(skipped)} stocks already bootstrapped, {len(stocks)} remaining")

    total = len(stocks)
    logger.info(f"Bootstrap: downloading {period} history for {total} stocks...")
    failed_symbols = []

    for idx, stock in enumerate(stocks, start=1):
        yf_sym = _yf_symbol(stock.symbol)
        try:
            df = yf.Ticker(yf_sym).history(period=period, auto_adjust=True)
            if df.empty:
                logger.warning(f"  {stock.symbol}: no data from yfinance, will try jugaad-data")
                failed_symbols.append(stock)
                continue

            df = df.reset_index()
            df["Date"] = pd.to_datetime(df["Date"]).dt.date

            rows = [
                {
                    "stock_id": stock.id,
                    "date": row["Date"],
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                }
                for _, row in df.iterrows()
                if row["Volume"] > 0
            ]

            inserted = _upsert_prices(db, rows)

            # Mirror to parquet archive
            parquet_df = df[df["Volume"] > 0][["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
            parquet_df.columns = ["date", "open", "high", "low", "close", "volume"]
            parquet_df.insert(0, "symbol", stock.symbol)
            append_prices(parquet_df)

            logger.debug(f"  {stock.symbol}: {inserted} rows")

        except Exception as e:
            logger.error(f"  {stock.symbol}: yfinance failed — {e}")
            failed_symbols.append(stock)

        if idx % 50 == 0:
            logger.info(f"  Progress: {idx}/{total} stocks")

    # Retry failed symbols with jugaad-data
    if failed_symbols:
        logger.info(f"Retrying {len(failed_symbols)} failed symbols with jugaad-data...")
        years = int(period.replace("y", "")) if period.endswith("y") else 10
        to_dt = date.today()
        from_dt = date(to_dt.year - years, to_dt.month, to_dt.day)

        for stock in failed_symbols:
            # Chunk by year for jugaad-data reliability
            chunk_start = from_dt
            all_rows = []
            while chunk_start < to_dt:
                chunk_end = min(
                    date(chunk_start.year + 1, chunk_start.month, chunk_start.day) - timedelta(days=1),
                    to_dt,
                )
                df = _fetch_jugaad_prices(stock.symbol, chunk_start, chunk_end)
                if not df.empty:
                    all_rows.append(df)
                chunk_start = chunk_end + timedelta(days=1)

            if not all_rows:
                logger.error(f"  {stock.symbol}: no data from jugaad-data either")
                continue

            full_df = pd.concat(all_rows, ignore_index=True)
            full_df = full_df.drop_duplicates(subset=["Date"])

            rows = [
                {
                    "stock_id": stock.id,
                    "date": row["Date"],
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                }
                for _, row in full_df.iterrows()
                if row["Volume"] > 0
            ]

            inserted = _upsert_prices(db, rows)

            parquet_df = full_df[full_df["Volume"] > 0][["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
            parquet_df.columns = ["date", "open", "high", "low", "close", "volume"]
            parquet_df.insert(0, "symbol", stock.symbol)
            append_prices(parquet_df)

            logger.info(f"  {stock.symbol} (jugaad-data): {inserted} rows")

    logger.info("Bootstrap prices complete.")


def ingest_daily_prices(db: Session, target_date: date) -> int:
    """
    Download and upsert OHLCV data for all active stocks for a single date.
    Uses NSE bulk CSV first (1 HTTP call), falls back to yfinance.
    Returns count of rows written.
    """
    from momentum_edge.data.nse_bulk import fetch_bhav_csv

    stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
    if not stocks:
        logger.warning("No active stocks in DB — run sync_stock_universe first")
        return 0

    symbol_to_id = {s.symbol: s.id for s in stocks}
    active_symbols = set(symbol_to_id.keys())

    logger.info(f"Downloading daily prices for {target_date} ({len(stocks)} stocks)...")

    # Try NSE bulk CSV first
    bulk_df = fetch_bhav_csv(target_date)

    if not bulk_df.empty:
        bulk_df = bulk_df[bulk_df["symbol"].isin(active_symbols)]

        rows = []
        for _, row in bulk_df.iterrows():
            stock_id = symbol_to_id.get(row["symbol"])
            if stock_id is None:
                continue
            vol = int(row["volume"]) if row["volume"] > 0 else 0
            if vol == 0:
                continue
            rows.append({
                "stock_id": stock_id,
                "date": target_date,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": vol,
            })

        written = _upsert_prices(db, rows)

        if rows:
            parquet_df = pd.DataFrame([
                {
                    "symbol": next(s.symbol for s in stocks if s.id == r["stock_id"]),
                    "date": r["date"],
                    "open": r["open"],
                    "high": r["high"],
                    "low": r["low"],
                    "close": r["close"],
                    "volume": r["volume"],
                }
                for r in rows
            ])
            append_prices(parquet_df)

        logger.info(f"  Daily prices written (bulk CSV): {written} stocks for {target_date}")
        return written

    # Fallback: yfinance
    logger.info("  Bulk CSV unavailable, falling back to yfinance...")

    symbols = [_yf_symbol(s.symbol) for s in stocks]
    start = (target_date - timedelta(days=1)).isoformat()
    end = (target_date + timedelta(days=1)).isoformat()

    try:
        raw = yf.download(
            tickers=symbols,
            start=start,
            end=end,
            auto_adjust=True,
            group_by="ticker",
            progress=False,
            threads=True,
        )
    except Exception as e:
        logger.error(f"yfinance bulk download failed: {e}")
        return 0

    rows = []
    for stock in stocks:
        yf_sym = _yf_symbol(stock.symbol)
        try:
            if len(symbols) == 1:
                df_stock = raw
            else:
                df_stock = raw[yf_sym] if yf_sym in raw.columns.get_level_values(0) else pd.DataFrame()

            if df_stock.empty:
                continue

            df_stock = df_stock.reset_index()
            df_stock["Date"] = pd.to_datetime(df_stock["Date"]).dt.date
            day_row = df_stock[df_stock["Date"] == target_date]

            if day_row.empty or day_row["Volume"].iloc[0] == 0:
                continue

            rows.append({
                "stock_id": stock.id,
                "date": target_date,
                "open": float(day_row["Open"].iloc[0]),
                "high": float(day_row["High"].iloc[0]),
                "low": float(day_row["Low"].iloc[0]),
                "close": float(day_row["Close"].iloc[0]),
                "volume": int(day_row["Volume"].iloc[0]),
            })
        except Exception as e:
            logger.debug(f"  {stock.symbol}: skipped — {e}")

    written = _upsert_prices(db, rows)

    if rows:
        parquet_df = pd.DataFrame([
            {
                "symbol": next(s.symbol for s in stocks if s.id == r["stock_id"]),
                "date": r["date"],
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
                "volume": r["volume"],
            }
            for r in rows
        ])
        append_prices(parquet_df)

    logger.info(f"  Daily prices written (yfinance): {written} stocks for {target_date}")
    return written
