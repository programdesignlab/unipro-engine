"""
M1 — Quarterly fundamentals & shareholding ingestion via Screener.in.

Authenticates with Screener.in, downloads Excel exports per company,
and parses:
  - Quarterly P&L: sales, net profit, operating profit, EPS
  - Balance sheet: borrowings, equity, reserves → D/E ratio
  - Shareholding pattern (from HTML): promoter, FII, DII, public %

Writes to:
  - DB: fundamentals table (upsert on stock_id + quarter)
  - DB: shareholding_pattern table (upsert on stock_id + quarter_end_date)
  - DB: stocks table (is_financial flag)
"""

from __future__ import annotations

import io
import re
import time
from datetime import date, datetime

import httpx
import pandas as pd
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.config import settings
from momentum_edge.db.models import Stock

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCREENER_BASE = "https://www.screener.in"
_LOGIN_URL = f"{_SCREENER_BASE}/login/"
_COMPANY_URL = f"{_SCREENER_BASE}/company"
_EXPORT_URL = f"{_SCREENER_BASE}/user/company/export"

_FINANCIAL_KEYWORDS = ("Bank", "NBFC", "Insurance", "Finance", "Financial")

# Excel "Data Sheet" row indices (0-based)
_ROW_FACE_VALUE = 6
_ROW_MARKET_CAP = 8
_ROW_ANNUAL_REPORT_DATE = 15
_ROW_ANNUAL_NET_PROFIT = 29
_ROW_QUARTERLY_HEADER = 39
_ROW_Q_REPORT_DATE = 40
_ROW_Q_SALES = 41
_ROW_Q_NET_PROFIT = 48
_ROW_Q_OPERATING_PROFIT = 49
_ROW_BS_HEADER = 54
_ROW_BS_REPORT_DATE = 55
_ROW_BS_EQUITY = 56
_ROW_BS_RESERVES = 57
_ROW_BS_BORROWINGS = 58
_ROW_BS_SHARES = 69
_ROW_BS_FACE_VALUE = 71
# v16 additions — cash flow & balance sheet details
_ROW_CF_HEADER = 73        # Cash Flow Statement section (approximate, may vary)
_ROW_BS_TRADE_RECEIVABLES = 61  # Trade receivables row (approximate)


# ---------------------------------------------------------------------------
# Quarter label helper
# ---------------------------------------------------------------------------


def _quarter_label(dt: date) -> str:
    """Convert a period-end date to Indian FY quarter label, e.g. 'Q3FY25'.

    Mar → Q4FYxx, Jun → Q1FY(xx+1), Sep → Q2FY(xx+1), Dec → Q3FY(xx+1).
    """
    month = dt.month
    year = dt.year
    if month <= 3:
        q, fy = 4, year - 1
    elif month <= 6:
        q, fy = 1, year
    elif month <= 9:
        q, fy = 2, year
    else:
        q, fy = 3, year
    return f"Q{q}FY{str(fy + 1)[-2:]}"


def _parse_screener_date(raw) -> date | None:
    """Parse date from Screener — handles datetime objects and strings."""
    if raw is None:
        return None
    # Handle datetime objects directly (from Excel)
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw

    raw_str = str(raw).strip()
    for fmt in ("%b %Y", "%B %Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(raw_str, fmt)
            if fmt in ("%b %Y", "%B %Y"):
                if dt.month == 12:
                    return date(dt.year, 12, 31)
                return date(dt.year, dt.month + 1, 1) - pd.Timedelta(days=1)
            return dt.date()
        except (ValueError, TypeError):
            continue
    return None


def _safe_float(val) -> float | None:
    """Convert a cell value to float, returning None for blanks/errors."""
    if val is None:
        return None
    try:
        f = float(val)
        if pd.isna(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# ScreenerClient
# ---------------------------------------------------------------------------


class ScreenerClient:
    """Authenticated Screener.in client for data export."""

    def __init__(self) -> None:
        self.client = httpx.Client(follow_redirects=True, timeout=30)
        self._logged_in = False

    # -- authentication -----------------------------------------------------

    def login(self) -> bool:
        """Login to Screener.in. Returns True on success."""
        if self._logged_in:
            return True

        try:
            login_page = self.client.get(_LOGIN_URL)
            login_page.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Screener login page fetch failed: {e}")
            return False

        match = re.search(r'csrfmiddlewaretoken.*?value="(.*?)"', login_page.text)
        if not match:
            logger.error("Could not extract CSRF token from Screener login page")
            return False

        csrf = match.group(1)
        resp = self.client.post(
            _LOGIN_URL,
            data={
                "username": settings.screener_userid,
                "password": settings.screener_password,
                "csrfmiddlewaretoken": csrf,
            },
            headers={"Referer": _LOGIN_URL},
        )

        # Screener redirects to / on success
        if resp.status_code == 200 and "Sign In" not in resp.text:
            self._logged_in = True
            logger.info("Screener.in login successful")
            return True

        logger.error("Screener.in login failed — check credentials")
        return False

    # -- company page helpers -----------------------------------------------

    def _fetch_company_page(self, symbol: str) -> tuple[str | None, str | None]:
        """Fetch company page HTML. Tries consolidated first, then standalone.

        Returns (html, page_url) or (None, None).
        """
        for suffix in ("/consolidated/", "/"):
            url = f"{_COMPANY_URL}/{symbol}{suffix}"
            try:
                resp = self.client.get(url)
                if resp.status_code == 200 and "export" in resp.text:
                    return resp.text, url
            except httpx.HTTPError:
                continue
        return None, None

    def get_export_id(self, symbol: str) -> tuple[int | None, str | None]:
        """Get the export ID for a company. Tries consolidated first, then standalone.

        Returns (export_id, page_url) or (None, None).
        """
        html, page_url = self._fetch_company_page(symbol)
        if html is None:
            return None, None

        match = re.search(r"export/(\d+)/", html)
        if match:
            return int(match.group(1)), page_url
        return None, None

    def download_excel(
        self, symbol: str, export_id: int, referer_url: str, *, save_raw: bool = True,
    ) -> bytes | None:
        """Download Excel export for a company. Optionally saves raw file to data/screener_exports/."""
        csrf2 = self.client.cookies.get("csrftoken")
        if not csrf2:
            logger.warning(f"  {symbol}: no csrftoken cookie for export download")
            return None

        url = f"{_EXPORT_URL}/{export_id}/"
        try:
            resp = self.client.post(
                url,
                data={"csrfmiddlewaretoken": csrf2},
                headers={"Referer": referer_url},
            )
            if resp.status_code == 200 and len(resp.content) > 500:
                if save_raw:
                    self._save_raw_excel(symbol, resp.content)
                return resp.content
            logger.warning(f"  {symbol}: export download returned status {resp.status_code}")
        except httpx.HTTPError as e:
            logger.warning(f"  {symbol}: export download failed — {e}")
        return None

    @staticmethod
    def _save_raw_excel(symbol: str, content: bytes) -> None:
        """Save raw Excel file to data/screener_exports/{SYMBOL}.xlsx."""
        from pathlib import Path

        out_dir = Path("data/screener_exports")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{symbol}.xlsx"
        path.write_bytes(content)

    @staticmethod
    def load_raw_excel(symbol: str) -> bytes | None:
        """Load previously saved raw Excel for a symbol. Returns None if not found."""
        from pathlib import Path

        path = Path("data/screener_exports") / f"{symbol}.xlsx"
        if path.exists():
            return path.read_bytes()
        return None

    # -- Excel parsing ------------------------------------------------------

    def parse_quarterly_fundamentals(self, symbol: str, excel_bytes: bytes) -> list[dict]:
        """Parse quarterly data from Excel Data Sheet.

        Returns list of dicts with:
        - quarter, period_end_date, sales, net_profit, operating_profit,
          eps, eps_yoy_growth, revenue_yoy_growth, net_margin
        """
        try:
            df = pd.read_excel(
                io.BytesIO(excel_bytes),
                sheet_name="Data Sheet",
                header=None,
                engine="openpyxl",
            )
        except Exception as e:
            logger.warning(f"  {symbol}: Excel parse error — {e}")
            return []

        # --- Extract quarterly row data ------------------------------------
        # Row 40: Report Date headers (period end dates)
        # Row 41: Sales
        # Row 48: Net profit
        # Row 49: Operating profit

        try:
            q_dates_row = df.iloc[_ROW_Q_REPORT_DATE, 1:]
            q_sales_row = df.iloc[_ROW_Q_SALES, 1:]
            q_net_profit_row = df.iloc[_ROW_Q_NET_PROFIT, 1:]
            q_op_profit_row = df.iloc[_ROW_Q_OPERATING_PROFIT, 1:]
        except IndexError:
            logger.warning(f"  {symbol}: quarterly rows missing in Excel")
            return []

        # Number of equity shares and face value from balance sheet section
        try:
            bs_shares_row = df.iloc[_ROW_BS_SHARES, 1:]
        except IndexError:
            bs_shares_row = pd.Series(dtype=float)

        # Use last available shares count for EPS calculation
        shares_values = [_safe_float(v) for v in bs_shares_row if _safe_float(v) is not None]
        latest_shares = shares_values[-1] if shares_values else None

        records: list[dict] = []

        for col_idx in range(len(q_dates_row)):
            raw_date = q_dates_row.iloc[col_idx]
            if pd.isna(raw_date):
                continue

            period_end = _parse_screener_date(raw_date)
            if period_end is None:
                continue

            sales = _safe_float(q_sales_row.iloc[col_idx])
            net_profit = _safe_float(q_net_profit_row.iloc[col_idx])
            op_profit = _safe_float(q_op_profit_row.iloc[col_idx])
            quarter = _quarter_label(period_end)

            # EPS = net_profit_cr * 1,00,00,000 / num_shares
            # Screener shares are in crores too, so: eps = net_profit_cr / shares_cr * 10
            # Actually: net_profit is in crores, shares from row 69 are raw counts
            # net_profit_cr * 10^7 / num_shares
            eps: float | None = None
            if net_profit is not None and latest_shares and latest_shares > 0:
                eps = round(net_profit * 1e7 / latest_shares, 2)

            # Net margin
            net_margin: float | None = None
            if net_profit is not None and sales and sales != 0:
                net_margin = round(net_profit / sales * 100, 2)

            # OPM (Operating Profit Margin %)
            opm: float | None = None
            if op_profit is not None and sales and sales != 0:
                opm = round(op_profit / sales * 100, 2)

            records.append({
                "quarter": quarter,
                "period_end_date": period_end,
                "sales": sales,
                "net_profit": net_profit,
                "operating_profit": op_profit,
                "eps": eps,
                "net_margin": net_margin,
                "opm": opm,
            })

        # --- YoY growth calculations (same quarter, 4 quarters back) -------
        for i, rec in enumerate(records):
            rec["eps_yoy_growth"] = None
            rec["revenue_yoy_growth"] = None

            # Find same quarter label one year back
            for j in range(i + 1, len(records)):
                prev = records[j]
                if prev["period_end_date"] is None or rec["period_end_date"] is None:
                    continue
                diff_days = (rec["period_end_date"] - prev["period_end_date"]).days
                # Should be ~365 days apart (allow 330–400 window)
                if 330 <= diff_days <= 400:
                    if rec["eps"] is not None and prev["eps"] and prev["eps"] != 0:
                        rec["eps_yoy_growth"] = round(
                            (rec["eps"] - prev["eps"]) / abs(prev["eps"]) * 100, 2
                        )
                    if rec["sales"] is not None and prev["sales"] and prev["sales"] != 0:
                        rec["revenue_yoy_growth"] = round(
                            (rec["sales"] - prev["sales"]) / abs(prev["sales"]) * 100, 2
                        )
                    break

        return records

    def parse_balance_sheet(self, excel_bytes: bytes) -> dict:
        """Parse latest balance sheet data.

        Returns dict with: borrowings, equity_share_capital, reserves, debt_to_equity.
        """
        result: dict = {
            "borrowings": None,
            "equity_share_capital": None,
            "reserves": None,
            "debt_to_equity": None,
        }

        try:
            df = pd.read_excel(
                io.BytesIO(excel_bytes),
                sheet_name="Data Sheet",
                header=None,
                engine="openpyxl",
            )
        except Exception:
            return result

        try:
            # Get last non-null column for latest period
            equity_row = df.iloc[_ROW_BS_EQUITY, 1:]
            reserves_row = df.iloc[_ROW_BS_RESERVES, 1:]
            borrowings_row = df.iloc[_ROW_BS_BORROWINGS, 1:]
        except IndexError:
            return result

        # Take latest available (last non-null value)
        def _latest(row: pd.Series) -> float | None:
            for val in reversed(list(row)):
                f = _safe_float(val)
                if f is not None:
                    return f
            return None

        equity = _latest(equity_row)
        reserves = _latest(reserves_row)
        borrowings = _latest(borrowings_row)

        result["equity_share_capital"] = equity
        result["reserves"] = reserves
        result["borrowings"] = borrowings

        if borrowings is not None and equity is not None and reserves is not None:
            total_equity = equity + reserves
            if total_equity != 0:
                result["debt_to_equity"] = round(borrowings / total_equity, 4)

        # v16: Trade receivables (approximate row — search by label)
        try:
            for row_idx in range(_ROW_BS_BORROWINGS + 1, min(_ROW_BS_SHARES, len(df))):
                cell = str(df.iloc[row_idx, 0]).strip().lower()
                if "trade receivable" in cell or "sundry debtor" in cell:
                    trade_recv = _latest(df.iloc[row_idx, 1:])
                    if trade_recv is not None:
                        result["trade_receivables"] = trade_recv
                    break
        except Exception:
            pass

        # v16: Cash from operating activities (search in cash flow section)
        try:
            for row_idx in range(_ROW_CF_HEADER, min(_ROW_CF_HEADER + 20, len(df))):
                cell = str(df.iloc[row_idx, 0]).strip().lower()
                if "cash from operating" in cell or "operating activity" in cell:
                    ocf = _latest(df.iloc[row_idx, 1:])
                    if ocf is not None:
                        result["ocf_cr"] = ocf
                    break
        except Exception:
            pass

        return result

    # -- Shareholding from HTML ---------------------------------------------

    def parse_shareholding(self, symbol: str) -> list[dict]:
        """Parse shareholding data from company page HTML.

        Returns list of dicts with:
        - quarter_end_date, promoter_pct, fii_pct, dii_pct, public_pct
        """
        html, _ = self._fetch_company_page(symbol)
        if html is None:
            return []

        # Extract the shareholding section
        sh_match = re.search(
            r'id="shareholding".*?<table.*?</table>', html, re.DOTALL
        )
        if not sh_match:
            logger.debug(f"  {symbol}: no shareholding section found")
            return []

        sh_html = sh_match.group(0)

        # Extract column headers (quarter dates like "Mar 2023", "Jun 2023")
        header_matches = re.findall(r"<th[^>]*>\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\s*</th>", sh_html)
        if not header_matches:
            logger.debug(f"  {symbol}: no shareholding quarter headers found")
            return []

        quarter_dates: list[date | None] = [_parse_screener_date(h) for h in header_matches]

        # Extract rows: Promoters, FIIs, DIIs, Public
        def _extract_row_pcts(label_pattern: str) -> list[float | None]:
            row_match = re.search(
                rf"{label_pattern}.*?</tr>", sh_html, re.DOTALL
            )
            if not row_match:
                return [None] * len(quarter_dates)
            row_html = row_match.group(0)
            pcts = re.findall(r"<td[^>]*>\s*([\d.]+)%?\s*</td>", row_html)
            return [_safe_float(p) for p in pcts]

        promoter_pcts = _extract_row_pcts(r"Promoters")
        fii_pcts = _extract_row_pcts(r"FII")
        dii_pcts = _extract_row_pcts(r"DII")
        public_pcts = _extract_row_pcts(r"Public")
        # Also try "Government" as some PSUs have it
        govt_pcts = _extract_row_pcts(r"Government")

        records: list[dict] = []
        for i, qd in enumerate(quarter_dates):
            if qd is None:
                continue
            records.append({
                "quarter_end_date": qd,
                "promoter_pct": promoter_pcts[i] if i < len(promoter_pcts) else None,
                "fii_pct": fii_pcts[i] if i < len(fii_pcts) else None,
                "dii_pct": dii_pcts[i] if i < len(dii_pcts) else None,
                "public_pct": (
                    (public_pcts[i] if i < len(public_pcts) else None)
                    or (govt_pcts[i] if i < len(govt_pcts) else None)
                ),
            })

        return records

    # -- cleanup ------------------------------------------------------------

    def close(self) -> None:
        self.client.close()
        self._logged_in = False


# ---------------------------------------------------------------------------
# DB upsert helpers
# ---------------------------------------------------------------------------


def _upsert_fundamentals(db: Session, rows: list[dict]) -> int:
    """Upsert quarterly fundamentals rows into DB."""
    if not rows:
        return 0
    db.execute(
        text("""
            INSERT INTO fundamentals (
                stock_id, quarter, eps, eps_yoy_growth, revenue, revenue_yoy_growth,
                net_margin, debt_to_equity, is_financial, reporting_date,
                opm, ocf_cr, trade_receivables_days
            )
            VALUES (
                :stock_id, :quarter, :eps, :eps_yoy_growth, :revenue, :revenue_yoy_growth,
                :net_margin, :debt_to_equity, :is_financial, :reporting_date,
                :opm, :ocf_cr, :trade_receivables_days
            )
            ON CONFLICT (stock_id, quarter) DO UPDATE SET
                eps               = EXCLUDED.eps,
                eps_yoy_growth    = EXCLUDED.eps_yoy_growth,
                revenue           = EXCLUDED.revenue,
                revenue_yoy_growth= EXCLUDED.revenue_yoy_growth,
                net_margin        = EXCLUDED.net_margin,
                debt_to_equity    = EXCLUDED.debt_to_equity,
                is_financial      = EXCLUDED.is_financial,
                reporting_date    = EXCLUDED.reporting_date,
                opm               = EXCLUDED.opm,
                ocf_cr            = EXCLUDED.ocf_cr,
                trade_receivables_days = EXCLUDED.trade_receivables_days,
                updated_at        = now()
        """),
        rows,
    )
    db.commit()
    return len(rows)


def _upsert_shareholding(db: Session, rows: list[dict]) -> int:
    """Upsert shareholding pattern rows into DB."""
    if not rows:
        return 0
    db.execute(
        text("""
            INSERT INTO shareholding_pattern (
                stock_id, quarter_end_date, promoter_pct, fii_pct, dii_pct, public_pct
            )
            VALUES (
                :stock_id, :quarter_end_date, :promoter_pct, :fii_pct, :dii_pct, :public_pct
            )
            ON CONFLICT (stock_id, quarter_end_date) DO UPDATE SET
                promoter_pct = EXCLUDED.promoter_pct,
                fii_pct      = EXCLUDED.fii_pct,
                dii_pct      = EXCLUDED.dii_pct,
                public_pct   = EXCLUDED.public_pct
        """),
        rows,
    )
    db.commit()
    return len(rows)


def _update_stock_financial_flag(db: Session, stock: Stock) -> None:
    """Set is_financial on stocks table based on industry name."""
    industry = stock.industry or ""
    is_fin = any(kw.lower() in industry.lower() for kw in _FINANCIAL_KEYWORDS)
    if stock.is_financial != is_fin:
        db.execute(
            text("UPDATE stocks SET is_financial = :is_fin, updated_at = now() WHERE id = :sid"),
            {"is_fin": is_fin, "sid": stock.id},
        )
        db.commit()


def _update_stock_shareholding(db: Session, stock: Stock, latest: dict) -> None:
    """Update latest shareholding percentages on stocks table."""
    db.execute(
        text("""
            UPDATE stocks SET
                promoter_holding_pct = :promoter_pct,
                fii_holding_pct      = :fii_pct,
                dii_holding_pct      = :dii_pct,
                shareholding_date    = :quarter_end_date,
                updated_at           = now()
            WHERE id = :sid
        """),
        {
            "promoter_pct": latest.get("promoter_pct"),
            "fii_pct": latest.get("fii_pct"),
            "dii_pct": latest.get("dii_pct"),
            "quarter_end_date": latest.get("quarter_end_date"),
            "sid": stock.id,
        },
    )
    db.commit()


# ---------------------------------------------------------------------------
# Public sync function
# ---------------------------------------------------------------------------


def sync_screener_fundamentals(
    db: Session,
    symbols: list[str] | None = None,
    batch_size: int = 50,
) -> int:
    """Fetch and upsert quarterly fundamentals from Screener for active stocks.

    1. Login to Screener
    2. For each stock: get export ID, download Excel, parse quarters + balance sheet
    3. Upsert into fundamentals table
    4. Parse shareholding from HTML and upsert into shareholding_pattern table
    5. Update is_financial flag on stocks table based on industry

    Args:
        db: SQLAlchemy session.
        symbols: Optional list of symbols to sync. If None, syncs all active.
        batch_size: Max number of stocks to process per run.

    Returns:
        Total fundamentals rows written.
    """
    client = ScreenerClient()

    if not client.login():
        logger.error("Screener sync aborted — login failed")
        client.close()
        return 0

    stocks = db.query(Stock).filter(Stock.is_active.is_(True)).all()
    if symbols:
        symbol_set = set(symbols)
        stocks = [s for s in stocks if s.symbol in symbol_set]

    stocks = stocks[:batch_size]
    logger.info(f"Screener sync: processing {len(stocks)} stocks")

    total_fundamentals = 0
    total_shareholding = 0

    for idx, stock in enumerate(stocks):
        symbol = stock.symbol

        # Re-login every 100 stocks to avoid session expiry
        if idx > 0 and idx % 100 == 0:
            logger.info(f"  Re-authenticating Screener session (after {idx} stocks)...")
            client.close()
            client = ScreenerClient()
            if not client.login():
                logger.error("Screener re-login failed, aborting")
                break

        # -- Update is_financial flag ---------------------------------------
        _update_stock_financial_flag(db, stock)
        is_financial = any(kw.lower() in (stock.industry or "").lower() for kw in _FINANCIAL_KEYWORDS)

        # -- Get export ID (use cached or fetch + cache) --------------------
        export_id = stock.screener_export_id
        page_url = f"{_COMPANY_URL}/{symbol}/consolidated/"
        if export_id is None:
            export_id, page_url = client.get_export_id(symbol)
            if export_id is None:
                logger.warning(f"  {symbol}: no export ID found on Screener")
                time.sleep(2)
                continue
            # Cache the export ID for future runs
            db.execute(
                text("UPDATE stocks SET screener_export_id = :eid WHERE id = :sid"),
                {"eid": export_id, "sid": stock.id},
            )
            db.commit()
            logger.debug(f"  {symbol}: cached screener_export_id={export_id}")

        excel_bytes = client.download_excel(symbol, export_id, page_url or "")
        if excel_bytes is None:
            logger.warning(f"  {symbol}: Excel download failed")
            time.sleep(2)
            continue

        # -- Parse quarterly fundamentals -----------------------------------
        quarterly = client.parse_quarterly_fundamentals(symbol, excel_bytes)

        # -- Parse balance sheet for D/E + v16 fields -------------------------
        bs = client.parse_balance_sheet(excel_bytes)
        debt_to_equity = bs.get("debt_to_equity")
        ocf_cr = bs.get("ocf_cr")
        trade_receivables = bs.get("trade_receivables")

        # Calculate trade receivable days: (receivables / annual_sales) * 365
        trade_recv_days: float | None = None
        if trade_receivables is not None and quarterly:
            # Use most recent 4 quarters of sales for annualized revenue
            recent_sales = [q.get("sales") for q in quarterly[:4] if q.get("sales")]
            if recent_sales:
                annual_sales = sum(recent_sales) * (4 / len(recent_sales))
                if annual_sales > 0:
                    trade_recv_days = round(trade_receivables / annual_sales * 365, 1)

        # -- Build DB rows --------------------------------------------------
        fund_rows: list[dict] = []
        for q in quarterly:
            fund_rows.append({
                "stock_id": stock.id,
                "quarter": q["quarter"],
                "eps": q.get("eps"),
                "eps_yoy_growth": q.get("eps_yoy_growth"),
                "revenue": q.get("sales"),
                "revenue_yoy_growth": q.get("revenue_yoy_growth"),
                "net_margin": q.get("net_margin"),
                "debt_to_equity": debt_to_equity,
                "is_financial": is_financial,
                "reporting_date": q.get("period_end_date"),
                "opm": q.get("opm"),
                "ocf_cr": ocf_cr,
                "trade_receivables_days": trade_recv_days,
            })

        written = _upsert_fundamentals(db, fund_rows)
        total_fundamentals += written

        # -- Parse and upsert shareholding ----------------------------------
        sh_records = client.parse_shareholding(symbol)
        if sh_records:
            sh_rows = [{"stock_id": stock.id, **r} for r in sh_records]
            sh_written = _upsert_shareholding(db, sh_rows)
            total_shareholding += sh_written

            # Update stocks table with latest shareholding
            latest_sh = sh_records[-1]
            _update_stock_shareholding(db, stock, latest_sh)

        # -- Logging --------------------------------------------------------
        if (idx + 1) % 10 == 0:
            logger.info(f"  Progress: {idx + 1}/{len(stocks)} stocks processed")

        # Rate limiting — 3s to avoid Screener throttling
        time.sleep(3)

    client.close()
    logger.info(
        f"Screener sync complete: {total_fundamentals} fundamental rows, "
        f"{total_shareholding} shareholding rows written"
    )
    return total_fundamentals
