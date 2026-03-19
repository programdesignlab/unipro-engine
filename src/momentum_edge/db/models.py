"""SQLAlchemy ORM models for MomentumEdge — v7 schema."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from momentum_edge.db.session import Base


# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------


class SectorData(Base):
    """NSE sector classification master."""

    __tablename__ = "sector_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sector_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    parent_sector: Mapped[str | None] = mapped_column(String(100))


class Stock(Base):
    """NSE-listed equity master data."""

    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sector_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sector_data.id"), index=True)
    sector: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))
    isin: Mapped[str | None] = mapped_column(String(12), unique=True)
    market_cap: Mapped[float | None] = mapped_column(Float)  # in crores
    exchange: Mapped[str] = mapped_column(String(10), default="NSE")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # v7 additions
    free_float_pct: Mapped[float | None] = mapped_column(Float)
    avg_daily_tv_cr: Mapped[float | None] = mapped_column(Float)
    is_asm: Mapped[bool] = mapped_column(Boolean, default=False)
    is_esm: Mapped[bool] = mapped_column(Boolean, default=False)
    is_financial: Mapped[bool] = mapped_column(Boolean, default=False)
    is_fii_capped_sector: Mapped[bool] = mapped_column(Boolean, default=False)
    promoter_holding_pct: Mapped[float | None] = mapped_column(Float)
    fii_holding_pct: Mapped[float | None] = mapped_column(Float)
    dii_holding_pct: Mapped[float | None] = mapped_column(Float)
    fii_headroom_pct: Mapped[float | None] = mapped_column(Float)
    is_fii_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    is_fii_cautioned: Mapped[bool] = mapped_column(Boolean, default=False)
    shareholding_date: Mapped[date | None] = mapped_column(Date)
    listing_date: Mapped[date | None] = mapped_column(Date)
    delisted_date: Mapped[date | None] = mapped_column(Date)
    screener_export_id: Mapped[int | None] = mapped_column(Integer)  # Screener.in company export ID

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ---------------------------------------------------------------------------
# Price & delivery data
# ---------------------------------------------------------------------------


class EODPrice(Base):
    """End-of-day OHLCV price data — sourced from NSE bhav copy."""

    __tablename__ = "eod_prices"
    __table_args__ = (UniqueConstraint("stock_id", "date", name="uq_eod_stock_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # v7 additions
    adj_close: Mapped[float | None] = mapped_column(Float)
    adj_factor: Mapped[float | None] = mapped_column(Float, default=1.0)
    traded_value_cr: Mapped[float | None] = mapped_column(Float)
    hit_upper_circuit: Mapped[bool] = mapped_column(Boolean, default=False)
    hit_lower_circuit: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DeliveryData(Base):
    """NSE daily delivery statistics per stock. Stored and displayed, NOT scored in v7."""

    __tablename__ = "delivery_data"
    __table_args__ = (UniqueConstraint("stock_id", "date", name="uq_delivery_stock_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    delivery_qty: Mapped[int | None] = mapped_column(BigInteger)
    delivery_pct: Mapped[float | None] = mapped_column(Float)  # 0–100
    traded_qty: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# Corporate actions
# ---------------------------------------------------------------------------


class CorporateAction(Base):
    """Stock splits, bonuses, rights — needed for adj_close calculation."""

    __tablename__ = "corporate_actions"
    __table_args__ = (
        UniqueConstraint("stock_id", "ex_date", "action_type", name="uq_corpaction_stock_date_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    ex_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)  # split, bonus, rights
    ratio_from: Mapped[int | None] = mapped_column(Integer)  # e.g. 1 (in 1:5 split)
    ratio_to: Mapped[int | None] = mapped_column(Integer)    # e.g. 5
    adj_factor: Mapped[float | None] = mapped_column(Float)  # multiplier
    raw_data: Mapped[str | None] = mapped_column(Text)       # original NSE description
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------------------------


class Fundamentals(Base):
    """Quarterly fundamental data — from Screener.in CSV."""

    __tablename__ = "fundamentals"
    __table_args__ = (UniqueConstraint("stock_id", "quarter", name="uq_fundamentals_stock_quarter"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    quarter: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "Q3FY25"
    eps: Mapped[float | None] = mapped_column(Float)
    eps_yoy_growth: Mapped[float | None] = mapped_column(Float)   # %
    revenue: Mapped[float | None] = mapped_column(Float)           # crores
    revenue_yoy_growth: Mapped[float | None] = mapped_column(Float)  # %
    roe: Mapped[float | None] = mapped_column(Float)               # %
    net_margin: Mapped[float | None] = mapped_column(Float)        # %
    pe_ratio: Mapped[float | None] = mapped_column(Float)
    debt_to_equity: Mapped[float | None] = mapped_column(Float)

    # v7 additions
    reporting_date: Mapped[date | None] = mapped_column(Date)       # when results announced
    expected_result_date: Mapped[date | None] = mapped_column(Date) # upcoming results date
    analyst_revision: Mapped[float | None] = mapped_column(Float)
    is_financial: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ---------------------------------------------------------------------------
# Institutional data
# ---------------------------------------------------------------------------


class FIIDIIData(Base):
    """Daily FII/DII aggregate trading activity."""

    __tablename__ = "fii_dii_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    fii_buy_cr: Mapped[float | None] = mapped_column(Float)
    fii_sell_cr: Mapped[float | None] = mapped_column(Float)
    fii_net_cr: Mapped[float | None] = mapped_column(Float)
    dii_buy_cr: Mapped[float | None] = mapped_column(Float)
    dii_sell_cr: Mapped[float | None] = mapped_column(Float)
    dii_net_cr: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ShareholdingPattern(Base):
    """Quarterly shareholding pattern — from Screener.in."""

    __tablename__ = "shareholding_pattern"
    __table_args__ = (
        UniqueConstraint("stock_id", "quarter_end_date", name="uq_shareholding_stock_quarter"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    quarter_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    promoter_pct: Mapped[float | None] = mapped_column(Float)
    fii_pct: Mapped[float | None] = mapped_column(Float)
    dii_pct: Mapped[float | None] = mapped_column(Float)
    public_pct: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BulkDeal(Base):
    """Bulk and block deals from NSE."""

    __tablename__ = "bulk_deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    client_name: Mapped[str | None] = mapped_column(String(200))
    deal_type: Mapped[str | None] = mapped_column(String(10))  # buy / sell
    quantity: Mapped[int | None] = mapped_column(BigInteger)
    price: Mapped[float | None] = mapped_column(Float)
    is_institution: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str | None] = mapped_column(String(10))  # bulk / block
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# Indicators & scores
# ---------------------------------------------------------------------------


class Indicators(Base):
    """Calculated technical indicators per stock per day."""

    __tablename__ = "indicators"
    __table_args__ = (UniqueConstraint("stock_id", "date", name="uq_indicators_stock_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ma50: Mapped[float | None] = mapped_column(Float)
    ma150: Mapped[float | None] = mapped_column(Float)
    ma200: Mapped[float | None] = mapped_column(Float)
    rs_score: Mapped[float | None] = mapped_column(Float)   # relative strength vs Nifty 50
    atr: Mapped[float | None] = mapped_column(Float)        # average true range
    high_52w: Mapped[float | None] = mapped_column(Float)
    low_52w: Mapped[float | None] = mapped_column(Float)

    # v7 additions
    ma200_slope: Mapped[float | None] = mapped_column(Float)
    rs_rank: Mapped[int | None] = mapped_column(Integer)
    mom_3m: Mapped[float | None] = mapped_column(Float)
    mom_6m: Mapped[float | None] = mapped_column(Float)
    mom_12_1: Mapped[float | None] = mapped_column(Float)
    raw_score: Mapped[float | None] = mapped_column(Float)
    scaled_score: Mapped[float | None] = mapped_column(Float)
    vol_scalar: Mapped[float | None] = mapped_column(Float)
    mom_vol_20d: Mapped[float | None] = mapped_column(Float)
    mom_quality: Mapped[float | None] = mapped_column(Float)
    obv: Mapped[float | None] = mapped_column(Float)
    adl_ratio: Mapped[float | None] = mapped_column(Float)
    vol_ratio_20: Mapped[float | None] = mapped_column(Float)
    vol_ratio_50: Mapped[float | None] = mapped_column(Float)
    pct_from_high: Mapped[float | None] = mapped_column(Float)
    delivery_trend: Mapped[float | None] = mapped_column(Float)  # display only

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Scores(Base):
    """Daily module scores per stock."""

    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("stock_id", "date", name="uq_scores_stock_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    momentum_score: Mapped[float | None] = mapped_column(Float)
    fundamental_score: Mapped[float | None] = mapped_column(Float)
    sector_score: Mapped[float | None] = mapped_column(Float)
    technical_score: Mapped[float | None] = mapped_column(Float)
    accumulation_score: Mapped[float | None] = mapped_column(Float)
    breakout_score: Mapped[float | None] = mapped_column(Float)
    composite_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# Signals & watchlist
# ---------------------------------------------------------------------------


class Signal(Base):
    """Trading signals — lifecycle: Pending → Confirmed/Failed/Expired."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    signal_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    pattern_type: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="Pending")
    pivot_price: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    entry_zone_low: Mapped[float | None] = mapped_column(Float)
    entry_zone_high: Mapped[float | None] = mapped_column(Float)
    volume_ratio: Mapped[float | None] = mapped_column(Float)
    obv_slope: Mapped[float | None] = mapped_column(Float)
    obv_bonus: Mapped[int] = mapped_column(Integer, default=0)
    obv_divergence: Mapped[bool] = mapped_column(Boolean, default=False)
    adl_ratio: Mapped[float | None] = mapped_column(Float)
    inst_flow_signal: Mapped[str | None] = mapped_column(String(20))
    inst_flow_positive: Mapped[bool | None] = mapped_column(Boolean)
    base_length_days: Mapped[int | None] = mapped_column(Integer)
    base_depth_pct: Mapped[float | None] = mapped_column(Float)
    regime: Mapped[str | None] = mapped_column(String(20))
    crash_warning: Mapped[bool] = mapped_column(Boolean, default=False)
    earnings_date: Mapped[date | None] = mapped_column(Date)
    days_to_earnings: Mapped[int | None] = mapped_column(Integer)
    earnings_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    tier: Mapped[int | None] = mapped_column(Integer)
    composite_score: Mapped[float | None] = mapped_column(Float)
    vol_scalar: Mapped[float | None] = mapped_column(Float)
    fundamental_bonus: Mapped[int | None] = mapped_column(Integer)
    confirmed_date: Mapped[date | None] = mapped_column(Date)
    failed_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Watchlist(Base):
    """Daily ranked watchlist output."""

    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("date", "stock_id", name="uq_watchlist_date_stock"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    composite_score: Mapped[float | None] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer)
    pattern_type: Mapped[str | None] = mapped_column(String(50))
    regime: Mapped[str | None] = mapped_column(String(20))
    stop_loss_level: Mapped[float | None] = mapped_column(Float)
    sector_name: Mapped[str | None] = mapped_column(String(100))
    sector_rank: Mapped[int | None] = mapped_column(Integer)

    # v7 additions
    tier: Mapped[int | None] = mapped_column(Integer)
    signal_id: Mapped[int | None] = mapped_column(Integer)
    momentum_score: Mapped[float | None] = mapped_column(Float)
    fundamental_bonus: Mapped[int | None] = mapped_column(Integer)
    obv_bonus: Mapped[int | None] = mapped_column(Integer)
    adl_ratio: Mapped[float | None] = mapped_column(Float)
    delivery_trend: Mapped[float | None] = mapped_column(Float)  # display only
    inst_flow_signal: Mapped[str | None] = mapped_column(String(20))
    inst_flow_positive: Mapped[bool | None] = mapped_column(Boolean)
    entry_zone_low: Mapped[float | None] = mapped_column(Float)
    entry_zone_high: Mapped[float | None] = mapped_column(Float)
    suggested_size_pct: Mapped[float | None] = mapped_column(Float)
    vol_scalar: Mapped[float | None] = mapped_column(Float)
    earnings_date: Mapped[date | None] = mapped_column(Date)
    earnings_flag: Mapped[bool | None] = mapped_column(Boolean)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# Performance & backtesting
# ---------------------------------------------------------------------------


class PerformanceLog(Base):
    """Trade performance tracking — entry/exit/P&L."""

    __tablename__ = "performance_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    entry_date: Mapped[date | None] = mapped_column(Date)
    exit_date: Mapped[date | None] = mapped_column(Date)
    entry_price: Mapped[float | None] = mapped_column(Float)
    actual_fill: Mapped[float | None] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float)
    pnl_pct: Mapped[float | None] = mapped_column(Float)
    pnl_inr: Mapped[float | None] = mapped_column(Float)
    exit_reason: Mapped[str | None] = mapped_column(String(30))
    holding_days: Mapped[int | None] = mapped_column(Integer)
    max_gain_pct: Mapped[float | None] = mapped_column(Float)   # MFE
    max_loss_pct: Mapped[float | None] = mapped_column(Float)   # MAE
    pattern_type: Mapped[str | None] = mapped_column(String(20))
    regime_at_entry: Mapped[str | None] = mapped_column(String(20))
    vol_scalar_at_entry: Mapped[float | None] = mapped_column(Float)
    obv_bonus_at_entry: Mapped[int | None] = mapped_column(Integer)
    earnings_flagged: Mapped[bool | None] = mapped_column(Boolean)
    days_to_earnings: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BacktestResult(Base):
    """Backtest test results storage."""

    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    test_name: Mapped[str] = mapped_column(String(50), nullable=False)
    run_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    parameters: Mapped[dict | None] = mapped_column(JSONB)
    cagr: Mapped[float | None] = mapped_column(Float)
    nifty_alpha: Mapped[float | None] = mapped_column(Float)
    win_rate: Mapped[float | None] = mapped_column(Float)
    avg_win: Mapped[float | None] = mapped_column(Float)
    avg_loss: Mapped[float | None] = mapped_column(Float)
    expectancy_pct: Mapped[float | None] = mapped_column(Float)
    max_drawdown: Mapped[float | None] = mapped_column(Float)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float)
    calmar_ratio: Mapped[float | None] = mapped_column(Float)
    total_trades: Mapped[int | None] = mapped_column(Integer)
    avg_holding_days: Mapped[float | None] = mapped_column(Float)
    annual_returns: Mapped[dict | None] = mapped_column(JSONB)
    passed_gate: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)


class WalkforwardResult(Base):
    """Walk-forward validation fold results."""

    __tablename__ = "walkforward_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    window_type: Mapped[str] = mapped_column(String(20), nullable=False)  # expanding / rolling
    fold: Mapped[int] = mapped_column(Integer, nullable=False)
    train_start: Mapped[date | None] = mapped_column(Date)
    train_end: Mapped[date | None] = mapped_column(Date)
    test_start: Mapped[date | None] = mapped_column(Date)
    test_end: Mapped[date | None] = mapped_column(Date)
    is_sharpe: Mapped[float | None] = mapped_column(Float)
    oos_sharpe: Mapped[float | None] = mapped_column(Float)
    oos_is_ratio: Mapped[float | None] = mapped_column(Float)
    is_cagr: Mapped[float | None] = mapped_column(Float)
    oos_cagr: Mapped[float | None] = mapped_column(Float)
    passed_gate: Mapped[bool | None] = mapped_column(Boolean)


# ---------------------------------------------------------------------------
# Users & orders (Phase 2+)
# ---------------------------------------------------------------------------


class User(Base):
    """Subscriber accounts (Phase 2+)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(20), default="basic")
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Order(Base):
    """Zerodha auto-execution order log (Phase 2+)."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    qty: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    kite_order_id: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# Legacy — kept to avoid breaking existing migration
# ---------------------------------------------------------------------------


class ScanResult(Base):
    """Legacy scaffold table — superseded by scores + watchlist."""

    __tablename__ = "scan_results"
    __table_args__ = (UniqueConstraint("stock_id", "scan_date", name="uq_scan_stock_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    scan_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    passes_trend_template: Mapped[bool] = mapped_column(Boolean, default=False)
    rs_rank: Mapped[float | None] = mapped_column(Float)
    composite_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
