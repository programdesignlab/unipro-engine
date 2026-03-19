"""
M1 — NSE ASM/ESM surveillance list.

Fetches the Additional Surveillance Measure (ASM) and Enhanced Surveillance
Measure (ESM) lists from NSE. Stocks under surveillance have trading
restrictions and are excluded from the universe (v7 hard filter).

Run daily after market close.
"""

import httpx
from loguru import logger
from sqlalchemy.orm import Session

from momentum_edge.db.models import Stock

NSE_BASE = "https://www.nseindia.com"
ASM_ENDPOINT = f"{NSE_BASE}/api/reportASM"

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


def _extract_symbol(item: dict) -> str | None:
    """Extract symbol from an ASM/ESM item, handling varying key casing."""
    return (
        item.get("symbol")
        or item.get("SYMBOL")
        or item.get("Symbol")
        or item.get("name")
        or item.get("NAME")
        or None
    )


def _extract_stage(item: dict) -> str | None:
    """
    Extract the surveillance stage/type from an ASM item.

    ESM stocks are typically identified by a 'stage' or 'surveillanceFlag'
    field containing 'ESM' or a high stage number.
    """
    for key in ("stage", "Stage", "STAGE", "surveillanceFlag", "type", "TYPE"):
        val = item.get(key)
        if val is not None:
            return str(val).strip().upper()
    return None


def fetch_asm_list() -> set[str]:
    """
    Fetch current ASM (Additional Surveillance Measure) list from NSE.
    Returns set of symbols currently under ASM surveillance.
    """
    try:
        with httpx.Client(
            headers=NSE_HEADERS, timeout=30, follow_redirects=True
        ) as client:
            # Hit NSE homepage first to obtain session cookies
            client.get(NSE_BASE)
            resp = client.get(ASM_ENDPOINT)
            resp.raise_for_status()

        data = resp.json()
        symbols: set[str] = set()

        # The API returns a dict with 'longterm' and 'shortterm' lists
        for category in ("longterm", "shortterm"):
            items = data.get(category, [])
            if not isinstance(items, list):
                logger.warning(f"ASM '{category}' is not a list, skipping")
                continue
            for item in items:
                if isinstance(item, dict):
                    sym = _extract_symbol(item)
                    if sym:
                        symbols.add(sym.strip().upper())
                elif isinstance(item, str):
                    # Some API versions may return plain symbol strings
                    symbols.add(item.strip().upper())

        logger.info(f"Fetched ASM list: {len(symbols)} symbols under surveillance")
        return symbols

    except Exception as e:
        logger.error(f"Failed to fetch ASM list from NSE: {e}")
        raise


def _classify_asm_esm(data: dict) -> tuple[set[str], set[str]]:
    """
    Parse the ASM endpoint response and separate ASM vs ESM symbols.

    ESM (Enhanced Surveillance Measure) is stricter than ASM. The API
    may indicate ESM via a stage field (e.g. stage containing 'ESM')
    or by placing ESM stocks in the 'longterm' bucket.

    Returns (asm_symbols, esm_symbols). ESM symbols are NOT included
    in the ASM set — they are mutually exclusive.
    """
    asm_symbols: set[str] = set()
    esm_symbols: set[str] = set()

    for category in ("longterm", "shortterm"):
        items = data.get(category, [])
        if not isinstance(items, list):
            continue

        for item in items:
            if isinstance(item, str):
                asm_symbols.add(item.strip().upper())
                continue
            if not isinstance(item, dict):
                continue

            sym = _extract_symbol(item)
            if not sym:
                continue
            sym = sym.strip().upper()

            stage = _extract_stage(item)
            if stage and "ESM" in stage:
                esm_symbols.add(sym)
            else:
                asm_symbols.add(sym)

    # Ensure no overlap — ESM takes precedence
    asm_symbols -= esm_symbols

    return asm_symbols, esm_symbols


def sync_surveillance(db: Session) -> tuple[int, int]:
    """
    Update is_asm and is_esm flags on all active stocks.

    1. Fetch ASM list from NSE
    2. Set is_asm=True for stocks in the list
    3. Set is_asm=False for stocks NOT in the list (clear old flags)
    4. Return (asm_count, esm_count)

    Note: ESM is a stricter version of ASM. The NSE API may include both
    under the same endpoint. If we can distinguish them, set is_esm=True
    for ESM stocks.
    """
    try:
        with httpx.Client(
            headers=NSE_HEADERS, timeout=30, follow_redirects=True
        ) as client:
            client.get(NSE_BASE)
            resp = client.get(ASM_ENDPOINT)
            resp.raise_for_status()

        data = resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch ASM data for surveillance sync: {e}")
        raise

    asm_symbols, esm_symbols = _classify_asm_esm(data)

    logger.info(
        f"Surveillance sync: {len(asm_symbols)} ASM, {len(esm_symbols)} ESM symbols"
    )

    # Clear all existing flags first
    db.query(Stock).filter(Stock.is_active.is_(True), Stock.is_asm.is_(True)).update(
        {Stock.is_asm: False}, synchronize_session="fetch"
    )
    db.query(Stock).filter(Stock.is_active.is_(True), Stock.is_esm.is_(True)).update(
        {Stock.is_esm: False}, synchronize_session="fetch"
    )

    # Set ASM flags
    asm_count = 0
    if asm_symbols:
        asm_count = (
            db.query(Stock)
            .filter(Stock.is_active.is_(True), Stock.symbol.in_(asm_symbols))
            .update({Stock.is_asm: True}, synchronize_session="fetch")
        )

    # Set ESM flags
    esm_count = 0
    if esm_symbols:
        esm_count = (
            db.query(Stock)
            .filter(Stock.is_active.is_(True), Stock.symbol.in_(esm_symbols))
            .update({Stock.is_esm: True}, synchronize_session="fetch")
        )

    db.commit()

    logger.info(
        f"Surveillance sync complete: {asm_count} stocks flagged ASM, "
        f"{esm_count} stocks flagged ESM"
    )

    return asm_count, esm_count
