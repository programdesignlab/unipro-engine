"""Fetch delivery data for remaining stocks in small 3-month chunks with delays to avoid NSE rate limits."""
import time
from datetime import date, timedelta
from loguru import logger
from momentum_edge.db.session import SessionLocal
from momentum_edge.db.models import Stock
from momentum_edge.data.delivery import _fetch_delivery, _upsert_delivery
from momentum_edge.data.parquet_store import append_delivery
import pandas as pd

SYMBOLS = ["TCS", "TECHM", "TITAN", "ULTRACEMCO"]
CHUNK_MONTHS = 3
DELAY_SECS = 5  # pause between chunks to avoid rate limit

db = SessionLocal()
to_date = date.today()
from_date = date(to_date.year - 10, to_date.month, to_date.day)

for sym in SYMBOLS:
    stock = db.query(Stock).filter(Stock.symbol == sym, Stock.is_active == True).first()
    if not stock:
        logger.warning(f"{sym}: not found in DB, skipping")
        continue

    logger.info(f"=== {sym} ===")
    all_rows = []
    chunk_start = from_date

    while chunk_start < to_date:
        chunk_end = min(chunk_start + timedelta(days=90), to_date)
        logger.info(f"  {sym}: {chunk_start} → {chunk_end}")
        df = _fetch_delivery(sym, chunk_start, chunk_end)
        if not df.empty:
            all_rows.append(df)
            logger.info(f"  {sym}: got {len(df)} rows")
        else:
            logger.warning(f"  {sym}: empty for {chunk_start} → {chunk_end}")
        chunk_start = chunk_end + timedelta(days=1)
        time.sleep(DELAY_SECS)

    if not all_rows:
        logger.warning(f"  {sym}: no delivery data at all")
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
    logger.info(f"  {sym}: DONE — {len(db_rows)} rows written")

db.close()
logger.info("All done.")
