"""SQLAlchemy ORM models for MomentumEdge — full 10-table schema."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from momentum_edge.db.session import Base


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
    # Keep legacy columns from initial migration
    sector: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))
    isin: Mapped[str | None] = mapped_column(String(12), unique=True)
    market_cap: Mapped[float | None] = mapped_column(Float)  # in crores
    exchange: Mapped[str] = mapped_column(String(10), default="NSE")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


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
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DeliveryData(Base):
    """NSE daily delivery statistics per stock."""

    __tablename__ = "delivery_data"
    __table_args__ = (UniqueConstraint("stock_id", "date", name="uq_delivery_stock_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    delivery_qty: Mapped[int | None] = mapped_column(BigInteger)
    delivery_pct: Mapped[float | None] = mapped_column(Float)  # 0–100
    traded_qty: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Fundamentals(Base):
    """Quarterly fundamental data — from Screener.in / Tijori API."""

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
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


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
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Scores(Base):
    """Daily module scores per stock."""

    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("stock_id", "date", name="uq_scores_stock_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    momentum_score: Mapped[float | None] = mapped_column(Float)      # max 40
    fundamental_score: Mapped[float | None] = mapped_column(Float)   # max 25
    sector_score: Mapped[float | None] = mapped_column(Float)        # max 20
    technical_score: Mapped[float | None] = mapped_column(Float)     # max 15
    accumulation_score: Mapped[float | None] = mapped_column(Float)  # max 15
    breakout_score: Mapped[float | None] = mapped_column(Float)      # max 10
    composite_score: Mapped[float | None] = mapped_column(Float)     # max 125
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
    pattern_type: Mapped[str | None] = mapped_column(String(50))   # VCP, base, breakout, etc.
    regime: Mapped[str | None] = mapped_column(String(20))         # Bull / Neutral / Bear
    stop_loss_level: Mapped[float | None] = mapped_column(Float)
    sector_name: Mapped[str | None] = mapped_column(String(100))
    sector_rank: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class User(Base):
    """Subscriber accounts (Phase 2+)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(20), default="basic")  # basic / pro / premium
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)     # Zerodha key, AES-256
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
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/placed/filled/cancelled
    kite_order_id: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# Legacy placeholder — kept to avoid breaking existing migration
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
