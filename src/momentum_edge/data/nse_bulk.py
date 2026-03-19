"""
NSE bulk CSV downloader — fetches a single daily file containing all stocks.

Replaces per-stock fetching (jugaad-data/yfinance) for daily ingestion.
One HTTP request → all 500 stocks' OHLCV + delivery data.
"""

import io
from datetime import date
import httpx
import pandas as pd
from loguru import logger

# NSE requires browser-like headers to allow downloads
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
}


def _get_nse_client() -> httpx.Client:
    """Create an httpx client with NSE headers and cookie handling."""
    client = httpx.Client(
        headers=NSE_HEADERS,
        follow_redirects=True,
        timeout=30.0,
    )
    # Hit NSE homepage first to get cookies
    try:
        client.get("https://www.nseindia.com/")
    except Exception:
        pass
    return client


def fetch_bhav_csv(target_date: date) -> pd.DataFrame:
    """
    Download NSE bhav copy CSV for a given date. Returns all stocks' OHLCV.

    Returns DataFrame with columns: symbol, date, open, high, low, close, volume
    Returns empty DataFrame if file not available (holiday/weekend).
    """
    # Format date components
    dd = target_date.strftime("%d")
    mm = target_date.strftime("%m")
    yyyy = target_date.strftime("%Y")
    ddmmyyyy = target_date.strftime("%d%m%Y")
    mon = target_date.strftime("%b").upper()

    # Try multiple URL patterns (NSE changes these periodically)
    urls = [
        f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{ddmmyyyy}.csv",
        f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{yyyy}/{mon}/cm{dd}{mon}{yyyy}bhav.csv.zip",
    ]

    client = _get_nse_client()

    for url in urls:
        try:
            resp = client.get(url)
            if resp.status_code == 200:
                content = resp.content

                # Handle zip files
                if url.endswith(".zip"):
                    import zipfile

                    with zipfile.ZipFile(io.BytesIO(content)) as zf:
                        csv_name = zf.namelist()[0]
                        content = zf.read(csv_name)

                df = pd.read_csv(
                    io.BytesIO(content)
                    if isinstance(content, bytes)
                    else io.StringIO(content.decode())
                )

                # Normalize column names (strip whitespace)
                df.columns = df.columns.str.strip()

                # Filter to EQ series only
                series_col = next(
                    (c for c in df.columns if c.upper() in ("SERIES", "SERIEs")), None
                )
                if series_col:
                    df = df[df[series_col].str.strip() == "EQ"]

                # Map to our schema
                col_map = {}
                for col in df.columns:
                    cu = col.upper().strip()
                    if cu == "SYMBOL":
                        col_map[col] = "symbol"
                    elif cu in ("OPEN_PRICE", "OPEN"):
                        col_map[col] = "open"
                    elif cu in ("HIGH_PRICE", "HIGH"):
                        col_map[col] = "high"
                    elif cu in ("LOW_PRICE", "LOW"):
                        col_map[col] = "low"
                    elif cu in ("CLOSE_PRICE", "CLOSE"):
                        col_map[col] = "close"
                    elif cu in ("TTL_TRD_QNTY", "TOTTRDQTY", "TOTAL_TRADE_QUANTITY"):
                        col_map[col] = "volume"
                    elif cu in ("DELIV_QTY", "DELIVERY_QTY", "TTL_DELIVRY_QTY"):
                        col_map[col] = "delivery_qty"
                    elif cu in ("DELIV_PER", "DELIVERY_PER", "%_DLVRY_QTY"):
                        col_map[col] = "delivery_pct"

                result = df.rename(columns=col_map)

                # Keep only columns we need
                keep = [
                    c
                    for c in [
                        "symbol",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "delivery_qty",
                        "delivery_pct",
                    ]
                    if c in result.columns
                ]
                result = result[keep].copy()
                result["date"] = target_date

                # Clean up
                result["symbol"] = result["symbol"].str.strip()
                for col in ["open", "high", "low", "close"]:
                    if col in result.columns:
                        result[col] = pd.to_numeric(result[col], errors="coerce")
                for col in ["volume", "delivery_qty"]:
                    if col in result.columns:
                        result[col] = (
                            pd.to_numeric(result[col], errors="coerce")
                            .fillna(0)
                            .astype(int)
                        )
                if "delivery_pct" in result.columns:
                    result["delivery_pct"] = pd.to_numeric(
                        result["delivery_pct"], errors="coerce"
                    )

                # Drop rows with missing critical data
                result = result.dropna(
                    subset=["symbol", "open", "high", "low", "close"]
                )

                logger.info(
                    f"NSE bhav CSV: {len(result)} EQ stocks for {target_date}"
                )
                client.close()
                return result.reset_index(drop=True)

        except Exception as e:
            logger.debug(f"  URL failed: {url} — {e}")
            continue

    client.close()
    logger.warning(f"NSE bhav CSV not available for {target_date}")
    return pd.DataFrame()


def fetch_bhav_csv_range(from_date: date, to_date: date) -> pd.DataFrame:
    """
    Download NSE bhav CSVs for a date range. Skips weekends.
    Returns combined DataFrame for all trading days in range.
    """
    from momentum_edge.utils.date_utils import trading_days_between

    all_dfs = []
    dates = trading_days_between(from_date, to_date)

    logger.info(
        f"Fetching NSE bhav CSVs: {from_date} → {to_date} ({len(dates)} trading days)"
    )

    for i, d in enumerate(dates):
        df = fetch_bhav_csv(d)
        if not df.empty:
            all_dfs.append(df)
        if (i + 1) % 50 == 0:
            logger.info(f"  Progress: {i + 1}/{len(dates)} days fetched")

    if not all_dfs:
        return pd.DataFrame()

    combined = pd.concat(all_dfs, ignore_index=True)
    logger.info(
        f"NSE bhav CSV range: {len(combined)} total rows across {len(all_dfs)} trading days"
    )
    return combined
