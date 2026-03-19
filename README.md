# MomentumEdge

Automated NSE stock scanning and ranking system using evidence-based momentum methodology for Indian equities.

## What it does

- Scans **Nifty 500** stocks daily using multi-timeframe momentum + volatility scaling
- Generates a ranked watchlist of breakout candidates with entry zones and stop losses
- **6-signal market regime detection** with crash indicator (Dierkes & Krupski 2022)
- **8-condition Minervini trend template** screening
- **VCP/base pattern detection** with OBV confirmation and circuit breaker exclusion
- **Smart institutional flow** signals (FII/DII/bulk deals based on promoter holding)
- **Fundamental bonus scoring** (EPS acceleration, not CANSLIM hard filters)
- Full backtesting framework (10 structured tests + walk-forward validation)
- REST API for frontend integration

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12, `uv` package manager |
| Database | PostgreSQL — Neon (prod), local Homebrew (dev) |
| API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 + Alembic migrations |
| Compute | Railway (cron + web service) |
| Data | NSE bulk CSV, yfinance, Screener.in |
| Email | Resend API |
| Storage | AWS S3 (parquet archive) |

## Quick Start

```bash
uv sync
cp .env.example .env  # edit with your credentials
PYTHONPATH=src uv run alembic upgrade head
PYTHONPATH=src uv run python main.py sync-universe --index nifty500
PYTHONPATH=src uv run python main.py bootstrap
PYTHONPATH=src uv run python main.py bootstrap-delivery-bulk
PYTHONPATH=src uv run python main.py sync-screener
PYTHONPATH=src uv run python main.py run
PYTHONPATH=src uv run python main.py watchlist
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `status` | DB connection + row counts |
| `sync-universe --index nifty500` | Sync Nifty 500 stocks |
| `bootstrap` | Bootstrap 10yr OHLCV prices |
| `bootstrap-delivery-bulk` | Bootstrap 2yr delivery data |
| `sync-screener` | Sync fundamentals from Screener.in |
| `ingest --date YYYY-MM-DD` | Daily data ingestion |
| `run --date YYYY-MM-DD` | Full pipeline (M1-M10) |
| `watchlist --date YYYY-MM-DD` | View ranked watchlist |
| `backtest` | Run full backtest |
| `backtest-tests` | Run structured tests (T1-T10) |

## API Endpoints

Production: `https://unipro-engine-production.up.railway.app`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/watchlist` | Ranked watchlist |
| GET | `/api/v1/scores/{symbol}` | Score breakdown |
| GET | `/api/v1/regime` | Market regime |
| GET | `/api/v1/sectors` | Sector rankings |
| GET | `/api/v1/stocks` | Stock universe |

## Environment Variables

See `.env.example` for the full list.
