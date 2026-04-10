"""
M1 — NSE delivery data ingestion.

Two ingestion strategies:
  - NSE bulk CSV: single file per day with ALL stocks (used for daily + recent bootstrap)
  - jugaad-data: per-stock scraper (used for older historical data beyond NSE archives)

bootstrap_delivery(): pull full history — bulk CSV for last 2yr, jugaad-data for older
ingest_daily_delivery(): single-day update via NSE bulk CSV (1 HTTP call for all stocks)
"""

from datetime import date, timedelta

import pandas as pd
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.models import Stock
def append_delivery(df):
    """Legacy parquet store stub — no-op."""
    pass


def _fetch_delivery(symbol: str, from_date: date, to_date: date) -> pd.DataFrame:
    """
    Fetch delivery data for a single symbol via jugaad-data.
    Returns DataFrame with columns: symbol, date, delivery_qty, delivery_pct, traded_qty
    Returns empty DataFrame on failure.
    """
    try:
        import concurrent.futures

        def _do_fetch():
            return nse_stock_df(
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                series="EQ",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_fetch)
            raw = future.result(timeout=45)  # 45 second timeout per chunk

        if raw is None or raw.empty:
            return pd.DataFrame()

        df = raw[["DATE", "DELIVERY QTY", "DELIVERY %", "VOLUME"]].copy()
        df.columns = ["date", "delivery_qty", "delivery_pct", "traded_qty"]
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df.insert(0, "symbol", symbol)
        df = df.dropna(subset=["delivery_qty", "delivery_pct"])
        df["delivery_qty"] = df["delivery_qty"].astype(int)
        df["delivery_pct"] = df["delivery_pct"].astype(float)
        df["traded_qty"] = df["traded_qty"].astype(int)
        return df.reset_index(drop=True)

    except concurrent.futures.TimeoutError:
        logger.warning(f"  {symbol}: delivery fetch timed out (45s)")
        return pd.DataFrame()
    except Exception as e:
        logger.warning(f"  {symbol}: delivery fetch failed — {e}")
        return pd.DataFrame()


def _upsert_delivery(db: Session, rows: list[dict]) -> int:
    """Bulk upsert delivery rows, deduplicating on (stock_id, date)."""
    if not rows:
        return 0
    db.execute(
        text("""
            INSERT INTO delivery_data (stock_id, date, delivery_qty, delivery_pct, traded_qty)
            VALUES (:stock_id, :date, :delivery_qty, :delivery_pct, :traded_qty)
            ON CONFLICT (stock_id, date) DO UPDATE SET
                delivery_qty = EXCLUDED.delivery_qty,
                delivery_pct = EXCLUDED.delivery_pct,
                traded_qty   = EXCLUDED.traded_qty
        """),
        rows,
    )
    db.commit()
    return len(rows)


def bootstrap_delivery(db: Session, symbols: list[str] | None = None, years: int = 10, skip_existing: bool = True) -> None:
    """
    Download full delivery history for all active stocks and load into delivery_data.
    Intended for one-time bootstrap. Fetches in annual chunks to stay within jugaad-data limits.
    Set skip_existing=True (default) to resume interrupted runs.
    """
    stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
    if symbols:
        stocks = [s for s in stocks if s.symbol in symbols]

    if skip_existing:
        from sqlalchemy import text as _text
        from datetime import timedelta
        # A stock is "done" only if it has recent data (within 30 days) — guards against partial ingestion
        cutoff = date.today() - timedelta(days=30)
        done = {r[0] for r in db.execute(
            _text("SELECT stock_id FROM delivery_data WHERE date >= :cutoff GROUP BY stock_id"),
            {"cutoff": cutoff}
        ).fetchall()}
        skipped = [s for s in stocks if s.id in done]
        stocks = [s for s in stocks if s.id not in done]
        if skipped:
            logger.info(f"Skipping {len(skipped)} stocks already fully ingested, resuming {len(stocks)} remaining")

    to_date = date.today()
    from_date = date(to_date.year - years, to_date.month, to_date.day)

    logger.info(f"Bootstrap delivery: {len(stocks)} stocks, {from_date} → {to_date}")

    for stock in stocks:
        all_rows = []

        # jugaad-data can be flaky on very large date ranges; chunk by year
        chunk_start = from_date
        while chunk_start < to_date:
            chunk_end = min(date(chunk_start.year + 1, chunk_start.month, chunk_start.day) - timedelta(days=1), to_date)
            df = _fetch_delivery(stock.symbol, chunk_start, chunk_end)
            if not df.empty:
                all_rows.append(df)
            chunk_start = chunk_end + timedelta(days=1)

        if not all_rows:
            logger.warning(f"  {stock.symbol}: no delivery data")
            continue

        full_df = pd.concat(all_rows, ignore_index=True)
        full_df = full_df.drop_duplicates(subset=["symbol", "date"])

        db_rows = [
            {
                "stock_id": stock.id,
                "date": row["date"],
                "delivery_qty": int(row["delivery_qty"]),
                "delivery_pct": float(row["delivery_pct"]),
                "traded_qty": int(row["traded_qty"]),
            }
            for _, row in full_df.iterrows()
        ]

        _upsert_delivery(db, db_rows)
        append_delivery(full_df)
        logger.debug(f"  {stock.symbol}: {len(db_rows)} rows")

    logger.info("Bootstrap delivery complete.")


def ingest_daily_delivery(db: Session, target_date: date) -> int:
    """
    Download and upsert delivery data for all active stocks for a single date.
    Uses NSE bulk CSV (1 HTTP call for all stocks).
    Falls back to jugaad-data per-stock if bulk CSV fails.
    Returns count of rows written.
    """
    from momentum_edge.data.nse_bulk import fetch_bhav_csv

    stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
    if not stocks:
        logger.warning("No active stocks in DB")
        return 0

    symbol_to_id = {s.symbol: s.id for s in stocks}
    active_symbols = set(symbol_to_id.keys())

    logger.info(f"Ingesting delivery data for {target_date} ({len(stocks)} stocks)...")

    # Try NSE bulk CSV first (1 request, all stocks)
    bulk_df = fetch_bhav_csv(target_date)

    if not bulk_df.empty and "delivery_qty" in bulk_df.columns:
        # Filter to active stocks only
        bulk_df = bulk_df[bulk_df["symbol"].isin(active_symbols)]
        bulk_df = bulk_df.dropna(subset=["delivery_qty", "delivery_pct"])

        db_rows = []
        parquet_rows = []
        for _, row in bulk_df.iterrows():
            stock_id = symbol_to_id.get(row["symbol"])
            if stock_id is None:
                continue
            db_rows.append({
                "stock_id": stock_id,
                "date": target_date,
                "delivery_qty": int(row["delivery_qty"]),
                "delivery_pct": float(row["delivery_pct"]),
                "traded_qty": int(row["volume"]) if "volume" in row.index else 0,
            })
            parquet_rows.append({
                "symbol": row["symbol"],
                "date": target_date,
                "delivery_qty": int(row["delivery_qty"]),
                "delivery_pct": float(row["delivery_pct"]),
                "traded_qty": int(row["volume"]) if "volume" in row.index else 0,
            })

        written = _upsert_delivery(db, db_rows)
        if parquet_rows:
            append_delivery(pd.DataFrame(parquet_rows))
        logger.info(f"  Delivery written (bulk CSV): {written} stocks for {target_date}")
        return written

    # Fallback: jugaad-data per-stock
    logger.info("  Bulk CSV unavailable, falling back to jugaad-data per-stock...")

    db_rows = []
    parquet_rows_list = []

    for stock in stocks:
        from_date = target_date - timedelta(days=3)
        to_date = target_date + timedelta(days=1)
        df = _fetch_delivery(stock.symbol, from_date, to_date)
        if df.empty:
            continue

        day = df[df["date"] == target_date]
        if day.empty:
            continue

        db_rows.append({
            "stock_id": stock.id,
            "date": target_date,
            "delivery_qty": int(day["delivery_qty"].iloc[0]),
            "delivery_pct": float(day["delivery_pct"].iloc[0]),
            "traded_qty": int(day["traded_qty"].iloc[0]),
        })
        parquet_rows_list.append(day)

    written = _upsert_delivery(db, db_rows)

    if parquet_rows_list:
        append_delivery(pd.concat(parquet_rows_list, ignore_index=True))

    logger.info(f"  Delivery written (jugaad-data): {written} stocks for {target_date}")
    return written


def bootstrap_delivery_bulk(db: Session, years: int = 2) -> None:
    """
    Bootstrap delivery data using NSE bulk CSV files (1 file per trading day).
    Much faster than jugaad-data per-stock: ~500 HTTP calls for 2 years vs 5,000+.

    NSE archives typically go back ~2 years. For older data, use bootstrap_delivery()
    which uses jugaad-data per-stock.

    Parameters
    ----------
    years : int
        Number of years of history to fetch (default 2, limited by NSE archive depth).
    """
    from momentum_edge.data.nse_bulk import fetch_bhav_csv
    from momentum_edge.utils.date_utils import trading_days_between

    stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
    symbol_to_id = {s.symbol: s.id for s in stocks}
    active_symbols = set(symbol_to_id.keys())

    to_date = date.today()
    from_date = date(to_date.year - years, to_date.month, to_date.day)
    dates = trading_days_between(from_date, to_date)

    logger.info(
        f"Bootstrap delivery (bulk CSV): {from_date} → {to_date}, "
        f"{len(dates)} trading days, {len(stocks)} active stocks"
    )

    total_written = 0
    days_fetched = 0

    for i, d in enumerate(dates):
        bulk_df = fetch_bhav_csv(d)
        if bulk_df.empty or "delivery_qty" not in bulk_df.columns:
            continue

        # Filter to active stocks with delivery data
        bulk_df = bulk_df[bulk_df["symbol"].isin(active_symbols)]
        bulk_df = bulk_df.dropna(subset=["delivery_qty", "delivery_pct"])

        if bulk_df.empty:
            continue

        db_rows = []
        parquet_rows = []
        for _, row in bulk_df.iterrows():
            stock_id = symbol_to_id.get(row["symbol"])
            if stock_id is None:
                continue
            db_rows.append({
                "stock_id": stock_id,
                "date": d,
                "delivery_qty": int(row["delivery_qty"]),
                "delivery_pct": float(row["delivery_pct"]),
                "traded_qty": int(row["volume"]) if "volume" in row.index else 0,
            })
            parquet_rows.append({
                "symbol": row["symbol"],
                "date": d,
                "delivery_qty": int(row["delivery_qty"]),
                "delivery_pct": float(row["delivery_pct"]),
                "traded_qty": int(row["volume"]) if "volume" in row.index else 0,
            })

        written = _upsert_delivery(db, db_rows)
        if parquet_rows:
            append_delivery(pd.DataFrame(parquet_rows))
        total_written += written
        days_fetched += 1

        if (i + 1) % 50 == 0:
            logger.info(f"  Progress: {i + 1}/{len(dates)} days, {total_written} rows written")

    logger.info(
        f"Bootstrap delivery (bulk CSV) complete: "
        f"{days_fetched} days fetched, {total_written} total rows"
    )
