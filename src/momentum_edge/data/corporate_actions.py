"""
Corporate actions fetcher — splits & bonuses from NSE API.

Fetches corporate action data, parses split/bonus ratios from description text,
calculates adj_factor per stock, and backfills adj_close for all existing price rows.
"""

import re
import time
from datetime import date, timedelta

import httpx
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.models import CorporateAction, EODPrice, Stock

# ---------------------------------------------------------------------------
# NSE HTTP client
# ---------------------------------------------------------------------------

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-actions",
    "X-Requested-With": "XMLHttpRequest",
}

NSE_CORP_ACTIONS_URL = (
    "https://www.nseindia.com/api/corporates-corporateActions"
    "?index=equities&from_date={from_date}&to_date={to_date}"
)


def _get_nse_client() -> httpx.Client:
    """Create httpx client with NSE headers and cookies."""
    client = httpx.Client(
        headers=NSE_HEADERS,
        follow_redirects=True,
        timeout=30.0,
    )
    # Hit NSE homepage first to get cookies (required for API access)
    try:
        client.get("https://www.nseindia.com/")
    except Exception:
        pass
    return client


# ---------------------------------------------------------------------------
# Ratio parsers
# ---------------------------------------------------------------------------

# Patterns for split descriptions — handles multiple NSE formats:
# "Stock Split From Rs.10/- To Rs.2/-"
# "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share"
# "Face Value Split (Sub-Division) - From Rs 5/- Per Share To Re 1/- Per Share"
_SPLIT_PATTERN = re.compile(
    r"(?:Rs\.?|Re\.?)\s*(\d+)(?:/-)?\s*(?:Per\s+Share\s*)?.*?(?:To|to)\s+(?:Rs\.?|Re\.?)\s*(\d+)",
    re.IGNORECASE,
)

# Patterns for bonus descriptions — handles "Bonus 1:1", "Bonus Issue 3:1", etc.
_BONUS_PATTERN = re.compile(
    r"Bonus\s+(?:Issue\s+)?(\d+)\s*:\s*(\d+)",
    re.IGNORECASE,
)


def _parse_split_ratio(subject: str) -> tuple[int, int, float] | None:
    """
    Parse split description to (from, to, adj_factor).

    "Stock Split From Rs.10/- To Rs.2/-" → (10, 2, 0.2)   # price divides by 5
    "Stock Split From Rs.5/- To Rs.1/-"  → (5, 1, 0.2)

    adj_factor = new_face_value / old_face_value

    Returns None if can't parse.
    """
    m = _SPLIT_PATTERN.search(subject)
    if not m:
        return None

    old_fv = int(m.group(1))
    new_fv = int(m.group(2))

    if old_fv <= 0 or new_fv <= 0 or new_fv >= old_fv:
        return None

    adj_factor = new_fv / old_fv
    return old_fv, new_fv, round(adj_factor, 6)


def _parse_bonus_ratio(subject: str) -> tuple[int, int, float] | None:
    """
    Parse bonus description to (bonus_shares, existing_shares, adj_factor).

    "Bonus 1:1"       → (1, 1, 0.5)    # 1 new for every 1 held, price halves
    "Bonus Issue 3:1" → (3, 1, 0.25)   # 3 new for every 1 held, price divides by 4
    "Bonus 1:2"       → (1, 2, 0.6667) # 1 new for every 2 held

    adj_factor = old_shares / new_total = to / (from + to)

    Returns None if can't parse.
    """
    m = _BONUS_PATTERN.search(subject)
    if not m:
        return None

    bonus_new = int(m.group(1))   # new shares issued
    bonus_held = int(m.group(2))  # per shares held

    if bonus_new <= 0 or bonus_held <= 0:
        return None

    adj_factor = bonus_held / (bonus_new + bonus_held)
    return bonus_new, bonus_held, round(adj_factor, 6)


# ---------------------------------------------------------------------------
# NSE API fetch
# ---------------------------------------------------------------------------


def fetch_corporate_actions(from_date: date, to_date: date) -> list[dict]:
    """
    Fetch corporate actions from NSE API for a date range.

    Returns list of dicts with: symbol, ex_date, action_type, ratio_from,
    ratio_to, adj_factor, raw_data.

    Only returns splits and bonuses (skips rights, dividends, AGM, etc.).
    """
    from_str = from_date.strftime("%d-%m-%Y")
    to_str = to_date.strftime("%d-%m-%Y")
    url = NSE_CORP_ACTIONS_URL.format(from_date=from_str, to_date=to_str)

    client = _get_nse_client()
    results: list[dict] = []

    try:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch corporate actions {from_str}–{to_str}: {e}")
        client.close()
        return results
    finally:
        client.close()

    if not isinstance(data, list):
        logger.warning(f"Unexpected response type: {type(data)}")
        return results

    for item in data:
        series = (item.get("series") or "").strip()
        if series != "EQ":
            continue

        symbol = (item.get("symbol") or "").strip()
        subject = (item.get("subject") or "").strip()
        ex_date_str = (item.get("exDate") or "").strip()

        if not symbol or not subject or not ex_date_str:
            continue

        # Parse ex_date — NSE format is "DD-Mon-YYYY" or "DD MMM YYYY"
        ex_dt = _parse_nse_date(ex_date_str)
        if ex_dt is None:
            logger.debug(f"Skipping unparseable date '{ex_date_str}' for {symbol}")
            continue

        subject_lower = subject.lower()

        # Try split
        if "split" in subject_lower:
            parsed = _parse_split_ratio(subject)
            if parsed:
                ratio_from, ratio_to, adj_factor = parsed
                results.append({
                    "symbol": symbol,
                    "ex_date": ex_dt,
                    "action_type": "split",
                    "ratio_from": ratio_from,
                    "ratio_to": ratio_to,
                    "adj_factor": adj_factor,
                    "raw_data": subject,
                })
            else:
                logger.debug(f"Could not parse split: {symbol} — '{subject}'")
            continue

        # Try bonus
        if "bonus" in subject_lower:
            parsed = _parse_bonus_ratio(subject)
            if parsed:
                ratio_from, ratio_to, adj_factor = parsed
                results.append({
                    "symbol": symbol,
                    "ex_date": ex_dt,
                    "action_type": "bonus",
                    "ratio_from": ratio_from,
                    "ratio_to": ratio_to,
                    "adj_factor": adj_factor,
                    "raw_data": subject,
                })
            else:
                logger.debug(f"Could not parse bonus: {symbol} — '{subject}'")
            continue

        # Skip everything else (dividends, AGM, rights, annual results, etc.)

    logger.info(
        f"NSE corporate actions {from_str}–{to_str}: "
        f"{len(results)} splits/bonuses from {len(data)} total entries"
    )
    return results


def _parse_nse_date(date_str: str) -> date | None:
    """Parse NSE date strings which come in various formats."""
    import datetime as dt

    formats = [
        "%d-%b-%Y",   # 15-Mar-2024
        "%d %b %Y",   # 15 Mar 2024
        "%d-%m-%Y",   # 15-03-2024
        "%d/%m/%Y",   # 15/03/2024
    ]
    date_str = date_str.strip().replace("  ", " ")
    for fmt in formats:
        try:
            return dt.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Sync to database
# ---------------------------------------------------------------------------


def sync_corporate_actions(db: Session, from_year: int = 2015) -> int:
    """
    Fetch and store all corporate actions from from_year to now.

    Chunks by year to avoid NSE API limits.
    Upserts on (stock_id, ex_date, action_type).
    Returns count of actions stored.
    """
    today = date.today()
    total_stored = 0

    # Build symbol → stock_id lookup
    stocks = db.query(Stock.id, Stock.symbol).all()
    symbol_to_id: dict[str, int] = {s.symbol: s.id for s in stocks}

    if not symbol_to_id:
        logger.warning("No stocks in DB — cannot sync corporate actions")
        return 0

    client = _get_nse_client()
    client.close()  # We create fresh clients per request in fetch_corporate_actions

    year = from_year
    while year <= today.year:
        chunk_start = date(year, 1, 1)
        chunk_end = min(date(year, 12, 31), today)

        logger.info(f"Fetching corporate actions for {year}...")
        actions = fetch_corporate_actions(chunk_start, chunk_end)

        stored_this_year = 0
        for action in actions:
            stock_id = symbol_to_id.get(action["symbol"])
            if stock_id is None:
                logger.debug(f"Symbol {action['symbol']} not in DB, skipping")
                continue

            # Upsert: check if exists
            existing = (
                db.query(CorporateAction)
                .filter(
                    CorporateAction.stock_id == stock_id,
                    CorporateAction.ex_date == action["ex_date"],
                    CorporateAction.action_type == action["action_type"],
                )
                .first()
            )

            if existing:
                # Update if adj_factor changed
                existing.ratio_from = action["ratio_from"]
                existing.ratio_to = action["ratio_to"]
                existing.adj_factor = action["adj_factor"]
                existing.raw_data = action["raw_data"]
            else:
                ca = CorporateAction(
                    stock_id=stock_id,
                    ex_date=action["ex_date"],
                    action_type=action["action_type"],
                    ratio_from=action["ratio_from"],
                    ratio_to=action["ratio_to"],
                    adj_factor=action["adj_factor"],
                    raw_data=action["raw_data"],
                )
                db.add(ca)
                stored_this_year += 1

        db.commit()
        total_stored += stored_this_year
        logger.info(f"  {year}: {stored_this_year} new actions stored")

        year += 1
        # Be polite to NSE — small delay between yearly chunks
        time.sleep(1.5)

    logger.info(f"Corporate actions sync complete: {total_stored} new actions stored")
    return total_stored


# ---------------------------------------------------------------------------
# Backfill adj_close
# ---------------------------------------------------------------------------


def backfill_adj_close(db: Session) -> int:
    """
    Calculate and backfill adj_close for ALL price rows using corporate actions.

    Algorithm:
    1. For each stock, get all corporate actions sorted by ex_date DESC
    2. Calculate cumulative adj_factor (multiply all factors from newest to oldest)
    3. For each price row:
       - If date >= all ex_dates: adj_close = close (no adjustment needed)
       - If date < an ex_date: adj_close = close * cumulative_factor_up_to_that_date
    4. Update in bulk using SQL UPDATE

    For stocks with NO corporate actions: adj_close = close, adj_factor = 1.0

    Returns count of rows updated.
    """
    total_updated = 0

    # Step 1: Set adj_close = close, adj_factor = 1.0 for ALL stocks with no
    # corporate actions (or as a baseline before applying adjustments)
    result = db.execute(
        text("""
            UPDATE eod_prices
            SET adj_close = close, adj_factor = 1.0
            WHERE adj_close IS NULL OR adj_factor IS NULL
        """)
    )
    baseline_count = result.rowcount
    db.commit()
    logger.info(f"Baseline: set adj_close=close for {baseline_count} rows with no adjustment")
    total_updated += baseline_count

    # Step 2: Get all stocks that have corporate actions
    stock_ids_with_actions = (
        db.query(CorporateAction.stock_id)
        .distinct()
        .all()
    )
    stock_ids_with_actions = [row[0] for row in stock_ids_with_actions]

    if not stock_ids_with_actions:
        logger.info("No corporate actions found — all stocks use unadjusted close")
        return total_updated

    logger.info(f"Backfilling adj_close for {len(stock_ids_with_actions)} stocks with corporate actions")

    for stock_id in stock_ids_with_actions:
        updated = _backfill_stock_adj_close(db, stock_id)
        total_updated += updated

    db.commit()
    logger.info(f"adj_close backfill complete: {total_updated} total rows updated")
    return total_updated


def _backfill_stock_adj_close(db: Session, stock_id: int) -> int:
    """
    Backfill adj_close for a single stock using its corporate actions.

    For prices on or after the most recent ex_date, adj_close = close.
    For prices before an ex_date, adj_close = close * cumulative adjustment factor.

    The cumulative factor is computed by multiplying adj_factors from newest
    action to oldest. Each action boundary adds another layer of adjustment
    for all prices before that ex_date.

    Returns count of rows updated.
    """
    # Get all corporate actions for this stock, sorted newest first
    actions = (
        db.query(CorporateAction)
        .filter(CorporateAction.stock_id == stock_id)
        .order_by(CorporateAction.ex_date.desc())
        .all()
    )

    if not actions:
        return 0

    # Build adjustment windows: list of (ex_date, cumulative_factor)
    # Cumulative factor accumulates from newest to oldest
    cumulative = 1.0
    windows: list[tuple[date, float]] = []
    for action in actions:
        cumulative *= action.adj_factor
        windows.append((action.ex_date, cumulative))

    # windows is sorted newest→oldest by ex_date
    # windows[0] = (newest_ex_date, factor_for_newest_action_only)
    # windows[-1] = (oldest_ex_date, product_of_all_factors)

    updated = 0

    # First: reset all prices on or after newest ex_date to unadjusted
    newest_ex = windows[0][0]
    result = db.execute(
        text("""
            UPDATE eod_prices
            SET adj_close = close, adj_factor = 1.0
            WHERE stock_id = :stock_id AND date >= :ex_date
        """),
        {"stock_id": stock_id, "ex_date": newest_ex},
    )
    updated += result.rowcount

    # Apply adjustments for each window
    for i, (ex_date, cum_factor) in enumerate(windows):
        # Determine the date range: from previous (older) ex_date up to this ex_date
        if i < len(windows) - 1:
            # There's an older action — apply cum_factor for dates in
            # [older_ex_date, this_ex_date)
            older_ex = windows[i + 1][0]
            result = db.execute(
                text("""
                    UPDATE eod_prices
                    SET adj_close = ROUND(CAST(close * :factor AS numeric), 2),
                        adj_factor = :factor
                    WHERE stock_id = :stock_id
                      AND date >= :from_date
                      AND date < :to_date
                """),
                {
                    "stock_id": stock_id,
                    "factor": round(cum_factor, 6),
                    "from_date": older_ex,
                    "to_date": ex_date,
                },
            )
            updated += result.rowcount
        else:
            # This is the oldest action — apply cum_factor for all dates before it
            result = db.execute(
                text("""
                    UPDATE eod_prices
                    SET adj_close = ROUND(CAST(close * :factor AS numeric), 2),
                        adj_factor = :factor
                    WHERE stock_id = :stock_id
                      AND date < :ex_date
                """),
                {
                    "stock_id": stock_id,
                    "factor": round(cum_factor, 6),
                    "ex_date": ex_date,
                },
            )
            updated += result.rowcount

    logger.debug(
        f"Stock {stock_id}: {len(actions)} corporate actions, "
        f"{updated} price rows adjusted"
    )
    return updated
