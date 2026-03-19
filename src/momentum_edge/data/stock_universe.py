"""
M1 — NSE stock universe management.

Maintains the list of NSE-listed stocks and syncs them to the DB.
Supports Nifty 50 (hardcoded) and Nifty 500 (fetched from NSE archives).
"""

import io

import httpx
import yfinance as yf
from loguru import logger
from sqlalchemy.orm import Session

from momentum_edge.db.models import SectorData, Stock

NIFTY500_CSV_URL = (
    "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
)

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://www.nseindia.com/",
}

# Current Nifty 50 constituents (as of early 2026)
NIFTY50_SYMBOLS = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", "BEL", "BHARTIARTL",
    "BPCL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY",
    "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE",
    "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ICICIPRULI",
    "INDUSINDBK", "INFY", "ITC", "JSWSTEEL", "KOTAKBANK",
    "LT", "LTIM", "M&M", "MARUTI", "NESTLEIND",
    "NTPC", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE",
    "SBIN", "SHRIRAMFIN", "SUNPHARMA", "TATACONSUM", "TATAMOTORS",
    "TATASTEEL", "TCS", "TECHM", "TITAN", "ULTRACEMCO",
]


def _yf_symbol(nse_symbol: str) -> str:
    """Convert NSE symbol to yfinance format."""
    return f"{nse_symbol}.NS"


def fetch_nifty500_symbols() -> list[str]:
    """
    Download the Nifty 500 constituent list CSV from NSE archives and
    return a list of symbols.

    Falls back to Nifty 50 symbols if the download or parsing fails.
    """
    try:
        with httpx.Client(headers=NSE_HEADERS, timeout=30, follow_redirects=True) as client:
            # Hit the NSE homepage first to get cookies
            client.get("https://www.nseindia.com/")
            resp = client.get(NIFTY500_CSV_URL)
            resp.raise_for_status()

        # CSV columns: Company Name, Industry, Symbol, Series, ISIN Code
        import csv

        reader = csv.DictReader(io.StringIO(resp.text))
        symbols: list[str] = []
        for row in reader:
            symbol = row.get("Symbol", "").strip()
            if symbol:
                symbols.append(symbol)

        if not symbols:
            raise ValueError("Parsed CSV but found no symbols")

        logger.info(f"Fetched {len(symbols)} Nifty 500 symbols from NSE")
        return symbols

    except Exception as e:
        logger.warning(
            f"Failed to fetch Nifty 500 list from NSE: {e}. "
            "Falling back to Nifty 50 symbols."
        )
        return list(NIFTY50_SYMBOLS)


def get_or_create_sector(db: Session, sector_name: str) -> int:
    """Return sector_id, creating sector row if it doesn't exist."""
    if not sector_name:
        sector_name = "Unknown"
    existing = db.query(SectorData).filter(SectorData.sector_name == sector_name).first()
    if existing:
        return existing.id
    sector = SectorData(sector_name=sector_name)
    db.add(sector)
    db.flush()
    return sector.id


def _sync_symbols(db: Session, symbols: list[str]) -> int:
    """
    Core sync logic: upsert stock rows for *symbols* using yfinance metadata.
    Returns count of upserted stocks.
    """
    upserted = 0
    total = len(symbols)

    logger.info(f"Syncing {total} stocks to DB...")

    for idx, symbol in enumerate(symbols, start=1):
        yf_sym = _yf_symbol(symbol)
        try:
            info = yf.Ticker(yf_sym).info
            name = info.get("longName") or info.get("shortName") or symbol
            sector_name = info.get("sector") or "Unknown"
            industry = info.get("industry")
            isin = info.get("isin")
            market_cap_inr = info.get("marketCap")
            market_cap_cr = round(market_cap_inr / 1e7, 2) if market_cap_inr else None
        except Exception as e:
            logger.warning(f"  Could not fetch info for {symbol}: {e}")
            name = symbol
            sector_name = "Unknown"
            industry = None
            isin = None
            market_cap_cr = None

        sector_id = get_or_create_sector(db, sector_name)

        existing = db.query(Stock).filter(Stock.symbol == symbol).first()
        if existing:
            existing.name = name
            existing.sector_id = sector_id
            existing.sector = sector_name
            existing.industry = industry
            existing.market_cap = market_cap_cr
            existing.exchange = "NSE"
            existing.is_active = True
        else:
            stock = Stock(
                symbol=symbol,
                name=name,
                sector_id=sector_id,
                sector=sector_name,
                industry=industry,
                isin=isin,
                market_cap=market_cap_cr,
                exchange="NSE",
                is_active=True,
            )
            db.add(stock)

        upserted += 1

        if idx % 50 == 0 or idx == total:
            logger.info(f"  Progress: {idx}/{total} stocks synced")

    db.commit()
    logger.info(f"  Stock universe sync complete: {upserted} stocks")
    return upserted


def sync_nifty500_universe(db: Session) -> int:
    """
    Fetch Nifty 500 constituents from NSE archives, sync to DB, and mark
    stocks no longer in the index as inactive.

    Returns count of synced stocks.
    """
    symbols = fetch_nifty500_symbols()
    synced = _sync_symbols(db, symbols)

    # Mark stocks NOT in the current Nifty 500 list as inactive
    deactivated = (
        db.query(Stock)
        .filter(Stock.exchange == "NSE", Stock.is_active.is_(True))
        .filter(Stock.symbol.notin_(symbols))
        .update({Stock.is_active: False}, synchronize_session="fetch")
    )
    if deactivated:
        db.commit()
        logger.info(f"  Deactivated {deactivated} stocks no longer in Nifty 500")

    return synced


def sync_stock_universe(
    db: Session,
    symbols: list[str] | None = None,
    *,
    index: str = "nifty50",
) -> int:
    """
    Sync the stock master list to DB using yfinance metadata.
    Creates or updates stock rows. Returns count of upserted stocks.

    Parameters
    ----------
    db : Session
        SQLAlchemy database session.
    symbols : list[str] | None
        Explicit symbol list. Overrides *index* when provided.
    index : str
        ``"nifty50"`` (default, backward-compatible) or ``"nifty500"``.
        Ignored when *symbols* is given.
    """
    if symbols is not None:
        return _sync_symbols(db, symbols)

    if index == "nifty500":
        return sync_nifty500_universe(db)

    return _sync_symbols(db, NIFTY50_SYMBOLS)
