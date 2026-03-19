"""
M1 — Quarterly fundamentals ingestion via yfinance.

Fetches per-stock:
  - Quarterly EPS, Revenue, Net Income, Gross Profit (from quarterly_income_stmt)
  - Quarterly Total Debt, Stockholders Equity (from quarterly_balance_sheet)
  - Trailing metrics: PE, ROE, profit margin, D/E (from ticker.info)

Writes to:
  - DB: fundamentals table
  - No parquet for fundamentals — small dataset, DB is sufficient
"""

from datetime import datetime

import pandas as pd
import yfinance as yf
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.models import Stock


def _yf_symbol(nse_symbol: str) -> str:
    return f"{nse_symbol}.NS"


def _quarter_label(dt) -> str:
    """Convert a datetime to quarter label e.g. 'Q3FY25'."""
    if pd.isna(dt):
        return "Unknown"
    dt = pd.Timestamp(dt)
    # Indian FY starts April; Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar
    month = dt.month
    year = dt.year
    if month in (4, 5, 6):
        q, fy = 1, year
    elif month in (7, 8, 9):
        q, fy = 2, year
    elif month in (10, 11, 12):
        q, fy = 3, year
    else:  # Jan, Feb, Mar
        q, fy = 4, year - 1
    return f"Q{q}FY{str(fy + 1)[-2:]}"


def _safe(series, key):
    """Safely get a scalar from a pandas Series, return None if missing."""
    try:
        val = series.get(key)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return float(val)
    except Exception:
        return None


def fetch_fundamentals(symbol: str) -> list[dict]:
    """
    Fetch quarterly fundamental data for one stock via yfinance.
    Returns list of dicts, one per quarter.
    """
    yf_sym = _yf_symbol(symbol)
    ticker = yf.Ticker(yf_sym)

    try:
        inc = ticker.quarterly_income_stmt   # columns = quarter dates
        bal = ticker.quarterly_balance_sheet
        info = ticker.info
    except Exception as e:
        logger.warning(f"  {symbol}: yfinance error — {e}")
        return []

    if inc is None or inc.empty:
        logger.warning(f"  {symbol}: no quarterly income data")
        return []

    quarters = inc.columns.tolist()
    records = []

    for i, qdate in enumerate(quarters):
        inc_q = inc[qdate]
        bal_q = bal[qdate] if (bal is not None and qdate in bal.columns) else pd.Series(dtype=float)

        total_revenue = _safe(inc_q, "Total Revenue")
        net_income = _safe(inc_q, "Net Income")
        gross_profit = _safe(inc_q, "Gross Profit")
        eps = _safe(inc_q, "Diluted EPS")
        total_debt = _safe(bal_q, "Total Debt")
        equity = _safe(bal_q, "Stockholders Equity")

        # YoY growth — compare to same quarter last year (4 quarters back)
        eps_yoy = None
        rev_yoy = None
        if i + 4 < len(quarters):
            prev_qdate = quarters[i + 4]
            prev_inc = inc[prev_qdate]
            prev_eps = _safe(prev_inc, "Diluted EPS")
            prev_rev = _safe(prev_inc, "Total Revenue")
            if eps is not None and prev_eps and prev_eps != 0:
                eps_yoy = round((eps - prev_eps) / abs(prev_eps) * 100, 2)
            if total_revenue is not None and prev_rev and prev_rev != 0:
                rev_yoy = round((total_revenue - prev_rev) / abs(prev_rev) * 100, 2)

        # Net margin
        net_margin = None
        if net_income is not None and total_revenue and total_revenue != 0:
            net_margin = round(net_income / total_revenue * 100, 2)

        # D/E ratio
        de_ratio = None
        if total_debt is not None and equity and equity != 0:
            de_ratio = round(total_debt / equity, 4)

        # ROE and PE come from .info (trailing, not per-quarter)
        roe = info.get("returnOnEquity")
        pe = info.get("trailingPE")

        records.append({
            "quarter": _quarter_label(qdate),
            "eps": eps,
            "eps_yoy_growth": eps_yoy,
            "revenue": round(total_revenue / 1e7, 2) if total_revenue else None,  # convert to crores
            "revenue_yoy_growth": rev_yoy,
            "roe": round(float(roe) * 100, 2) if roe else None,
            "net_margin": net_margin,
            "pe_ratio": round(float(pe), 2) if pe else None,
            "debt_to_equity": de_ratio,
        })

    return records


def _upsert_fundamentals(db: Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    db.execute(
        text("""
            INSERT INTO fundamentals (
                stock_id, quarter, eps, eps_yoy_growth, revenue, revenue_yoy_growth,
                roe, net_margin, pe_ratio, debt_to_equity
            )
            VALUES (
                :stock_id, :quarter, :eps, :eps_yoy_growth, :revenue, :revenue_yoy_growth,
                :roe, :net_margin, :pe_ratio, :debt_to_equity
            )
            ON CONFLICT (stock_id, quarter) DO UPDATE SET
                eps               = EXCLUDED.eps,
                eps_yoy_growth    = EXCLUDED.eps_yoy_growth,
                revenue           = EXCLUDED.revenue,
                revenue_yoy_growth= EXCLUDED.revenue_yoy_growth,
                roe               = EXCLUDED.roe,
                net_margin        = EXCLUDED.net_margin,
                pe_ratio          = EXCLUDED.pe_ratio,
                debt_to_equity    = EXCLUDED.debt_to_equity,
                updated_at        = now()
        """),
        rows,
    )
    db.commit()
    return len(rows)


def sync_fundamentals(db: Session, symbols: list[str] | None = None) -> None:
    """
    Fetch and upsert quarterly fundamentals for all active stocks.
    Safe to run repeatedly — upserts on (stock_id, quarter).
    """
    stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
    if symbols:
        stocks = [s for s in stocks if s.symbol in symbols]

    logger.info(f"Syncing fundamentals for {len(stocks)} stocks...")
    total = 0

    for stock in stocks:
        records = fetch_fundamentals(stock.symbol)
        if not records:
            continue

        db_rows = [{**r, "stock_id": stock.id} for r in records]
        written = _upsert_fundamentals(db, db_rows)
        total += written
        logger.debug(f"  {stock.symbol}: {written} quarters")

    logger.info(f"Fundamentals sync complete: {total} rows written")
