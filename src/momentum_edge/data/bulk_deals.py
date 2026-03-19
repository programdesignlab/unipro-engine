"""
Fetch bulk and block deals from NSE API.

Endpoint: https://www.nseindia.com/api/snapshot-capital-market-largedeal
Returns dict with BULK_DEALS_DATA and BLOCK_DEALS_DATA lists.
"""

from datetime import date, datetime

import httpx
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.data.nse_bulk import NSE_HEADERS, _get_nse_client
from momentum_edge.db.models import BulkDeal, Stock

# Known institutional names/patterns for is_institution flag
INSTITUTION_PATTERNS = [
    "MUTUAL FUND",
    "INSURANCE",
    "BANK",
    "SECURITIES",
    "CAPITAL",
    "ASSET MANAGEMENT",
    "AMC",
    "HDFC",
    "ICICI",
    "SBI",
    "KOTAK",
    "NIPPON",
    "AXIS",
    "BIRLA",
    "MOTILAL",
    "EDELWEISS",
    "GOLDMAN",
    "MORGAN",
    "CITIBANK",
    "BARCLAYS",
    "NOMURA",
    "CLSA",
]


def _is_institution(client_name: str) -> bool:
    """Check if client name matches known institutional patterns."""
    if not client_name:
        return False
    name_upper = client_name.upper()
    return any(pattern in name_upper for pattern in INSTITUTION_PATTERNS)


def _parse_nse_date(date_str: str) -> date:
    """Parse NSE date format 'DD-Mon-YYYY' (e.g. '19-Mar-2026')."""
    return datetime.strptime(date_str.strip(), "%d-%b-%Y").date()


def _to_float(value) -> float | None:
    """Convert NSE string value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _to_int(value) -> int | None:
    """Convert NSE string value to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (ValueError, TypeError):
        return None


def fetch_bulk_deals_today() -> list[dict]:
    """
    Fetch today's bulk and block deals from NSE.
    Returns list of dicts with: date, symbol, client_name, deal_type, quantity, price, source (bulk/block)
    """
    url = "https://www.nseindia.com/api/snapshot-capital-market-largedeal"
    client = _get_nse_client()

    try:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

        if not data or not isinstance(data, dict):
            logger.warning("Bulk deals API returned unexpected format")
            return []

        deals: list[dict] = []

        # Process both bulk and block deals
        for source_key, source_label in [
            ("BULK_DEALS_DATA", "bulk"),
            ("BLOCK_DEALS_DATA", "block"),
        ]:
            items = data.get(source_key, [])
            if not items:
                continue

            for item in items:
                try:
                    deal = {
                        "date": _parse_nse_date(item.get("date", "")),
                        "symbol": item.get("symbol", "").strip(),
                        "client_name": item.get("clientName", "").strip(),
                        "deal_type": item.get("buySell", "").strip().lower(),
                        "quantity": _to_int(item.get("qty")),
                        "price": _to_float(item.get("watp")),
                        "source": source_label,
                    }
                    if deal["symbol"]:
                        deals.append(deal)
                except Exception as e:
                    logger.debug(f"Skipping malformed deal entry: {e}")
                    continue

        logger.info(f"Bulk/block deals fetched: {len(deals)} deals")
        return deals

    except httpx.HTTPStatusError as e:
        logger.error(f"Bulk deals API HTTP error: {e.response.status_code}")
        return []
    except Exception as e:
        logger.error(f"Bulk deals fetch failed: {e}")
        return []
    finally:
        client.close()


def ingest_bulk_deals(db: Session, target_date: date | None = None) -> int:
    """
    Fetch and store today's bulk/block deals.
    Maps symbols to stock_id, flags is_institution.
    Returns count of deals stored.
    """
    deals = fetch_bulk_deals_today()
    if not deals:
        logger.info("Bulk deals: no deals to ingest")
        return 0

    # Build symbol → stock_id lookup from DB
    stocks = db.query(Stock.id, Stock.symbol).all()
    symbol_map: dict[str, int] = {s.symbol: s.id for s in stocks}

    count = 0
    for deal in deals:
        symbol = deal["symbol"]
        stock_id = symbol_map.get(symbol)

        if stock_id is None:
            logger.debug(f"Bulk deals: symbol '{symbol}' not found in stocks table, skipping")
            continue

        # Filter by target_date if specified
        if target_date and deal["date"] != target_date:
            continue

        record = BulkDeal(
            date=deal["date"],
            stock_id=stock_id,
            client_name=deal["client_name"],
            deal_type=deal["deal_type"],
            quantity=deal["quantity"],
            price=deal["price"],
            is_institution=_is_institution(deal["client_name"]),
            source=deal["source"],
        )
        db.add(record)
        count += 1

    if count > 0:
        db.commit()
        logger.info(f"Bulk deals: inserted {count} deals")
    else:
        logger.info("Bulk deals: no matching deals to store")

    return count
