"""
Fetch daily FII/DII aggregate trading data from NSE API.

Endpoint: https://www.nseindia.com/api/fiidiiTradeReact
Returns 2 items (FII and DII) with buyValue, sellValue, netValue.
"""

from datetime import date, datetime

import httpx
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.data.nse_bulk import NSE_HEADERS, _get_nse_client
from momentum_edge.db.models import FIIDIIData


def _parse_nse_date(date_str: str) -> date:
    """Parse NSE date format 'DD-Mon-YYYY' (e.g. '19-Mar-2026')."""
    return datetime.strptime(date_str.strip(), "%d-%b-%Y").date()


def _to_float(value) -> float | None:
    """Convert NSE string value to float, returning None on failure."""
    if value is None:
        return None
    try:
        # NSE sometimes uses commas in numbers
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def fetch_fii_dii_today() -> dict | None:
    """
    Fetch today's FII/DII data from NSE API.
    Returns dict with: date, fii_buy_cr, fii_sell_cr, fii_net_cr, dii_buy_cr, dii_sell_cr, dii_net_cr
    Values are in crores. Returns None if not available.
    """
    url = "https://www.nseindia.com/api/fiidiiTradeReact"
    client = _get_nse_client()

    try:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

        if not data or not isinstance(data, list) or len(data) < 2:
            logger.warning("FII/DII API returned unexpected format")
            return None

        result: dict = {}

        for item in data:
            category = item.get("category", "").strip().upper()
            if "FII" in category or "FPI" in category:
                result["fii_buy_cr"] = _to_float(item.get("buyValue"))
                result["fii_sell_cr"] = _to_float(item.get("sellValue"))
                result["fii_net_cr"] = _to_float(item.get("netValue"))
                if "date" not in result:
                    result["date"] = _parse_nse_date(item.get("date", ""))
            elif "DII" in category:
                result["dii_buy_cr"] = _to_float(item.get("buyValue"))
                result["dii_sell_cr"] = _to_float(item.get("sellValue"))
                result["dii_net_cr"] = _to_float(item.get("netValue"))
                if "date" not in result:
                    result["date"] = _parse_nse_date(item.get("date", ""))

        if "date" not in result:
            logger.warning("FII/DII: could not parse date from response")
            return None

        logger.info(
            f"FII/DII data for {result['date']}: "
            f"FII net={result.get('fii_net_cr')}, DII net={result.get('dii_net_cr')}"
        )
        return result

    except httpx.HTTPStatusError as e:
        logger.error(f"FII/DII API HTTP error: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"FII/DII fetch failed: {e}")
        return None
    finally:
        client.close()


def ingest_fii_dii(db: Session, target_date: date | None = None) -> bool:
    """
    Fetch and upsert FII/DII data for target_date (default: today).
    Returns True if data was written.
    """
    data = fetch_fii_dii_today()
    if data is None:
        logger.warning("FII/DII: no data returned from NSE")
        return False

    record_date = data["date"]

    # If caller specified a target_date, verify the fetched data matches
    if target_date and record_date != target_date:
        logger.warning(
            f"FII/DII: API returned date {record_date}, expected {target_date}"
        )
        # Still store it — NSE may return previous trading day's data
        record_date = data["date"]

    # Upsert: check if record exists for this date
    existing = db.query(FIIDIIData).filter(FIIDIIData.date == record_date).first()

    if existing:
        existing.fii_buy_cr = data.get("fii_buy_cr")
        existing.fii_sell_cr = data.get("fii_sell_cr")
        existing.fii_net_cr = data.get("fii_net_cr")
        existing.dii_buy_cr = data.get("dii_buy_cr")
        existing.dii_sell_cr = data.get("dii_sell_cr")
        existing.dii_net_cr = data.get("dii_net_cr")
        logger.info(f"FII/DII: updated existing record for {record_date}")
    else:
        record = FIIDIIData(
            date=record_date,
            fii_buy_cr=data.get("fii_buy_cr"),
            fii_sell_cr=data.get("fii_sell_cr"),
            fii_net_cr=data.get("fii_net_cr"),
            dii_buy_cr=data.get("dii_buy_cr"),
            dii_sell_cr=data.get("dii_sell_cr"),
            dii_net_cr=data.get("dii_net_cr"),
        )
        db.add(record)
        logger.info(f"FII/DII: inserted new record for {record_date}")

    db.commit()
    return True
