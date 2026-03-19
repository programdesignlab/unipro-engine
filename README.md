# MomentumEdge

Automated NSE stock scanning and ranking system using evidence-based momentum methodology.

## What it does

- Scans Nifty 500 stocks daily using multi-timeframe momentum + volatility scaling
- Generates a ranked watchlist of breakout candidates (max 20 per day)
- 6-signal market regime detection with crash indicator (Strong Bull / Bull / Weak / Bear / Full Bear)
- 8-condition Minervini trend template screening
- VCP/base pattern detection with OBV confirmation
- Smart institutional flow signals (FII/DII/bulk deals)
- Full backtesting framework (10 structured tests + walk-forward validation)

## Tech Stack

- **Python 3.12**, `uv` package manager
- **PostgreSQL** (Neon for prod, local for dev)
- **FastAPI** REST API (Railway deployment)
- **SQLAlchemy 2.0** + Alembic migrations
- **Data sources:** NSE bulk CSV, yfinance, Screener.in
- **Email:** Resend API
- **Storage:** AWS S3 (parquet archive)

## Quick Start

```bash
# Install dependencies
uv sync

# Copy and fill in environment variables
cp .env.example .env

# Run migrations
PYTHONPATH=src uv run alembic upgrade head

# Run pipeline for latest trading day
PYTHONPATH=src uv run python main.py run

# View watchlist
PYTHONPATH=src uv run python main.py watchlist

# Start API server
PYTHONPATH=src uv run uvicorn momentum_edge.api.app:app --reload --port 8000

# Run backtest
PYTHONPATH=src uv run python main.py backtest --start 2015-01-01 --end 2024-12-31
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `status` | DB connection + row counts + parquet file status |
| `sync-universe --index nifty500` | Sync Nifty 50 or Nifty 500 stock master list |
| `bootstrap` | Bootstrap 10yr OHLCV prices from yfinance |
| `bootstrap-delivery` | Bootstrap historical delivery data via jugaad-data |
| `bootstrap-delivery-bulk` | Bootstrap 2yr delivery data via NSE bulk CSV (fast) |
| `sync-fundamentals` | Sync quarterly fundamentals from yfinance (legacy) |
| `sync-screener` | Sync fundamentals + shareholding from Screener.in |
| `ingest --date YYYY-MM-DD` | Daily data ingestion (prices + delivery + index) |
| `run --date YYYY-MM-DD` | Full pipeline M1-M10 (ingest + scan + watchlist) |
| `scan --date YYYY-MM-DD` | Scan only: indicators + scoring (no ingestion) |
| `watchlist --date YYYY-MM-DD` | View ranked watchlist with score breakdown |
| `backtest` | Run full v7 backtest over historical data |
| `backtest-tests` | Run structured tests T1-T10 from v7 spec |

All commands run as: `PYTHONPATH=src uv run python main.py <command> [options]`

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/watchlist` | Today's ranked watchlist |
| GET | `/api/v1/scores/{symbol}` | Score breakdown for a stock |
| GET | `/api/v1/regime` | Current market regime |
| GET | `/api/v1/sectors` | Sector rotation rankings |
| GET | `/api/v1/stocks` | Stock universe |

Start the API server:

```bash
PYTHONPATH=src uv run uvicorn momentum_edge.api.app:app --reload --port 8000
```

## Pipeline Modules

| Module | File | Purpose | Max Pts |
|--------|------|---------|---------|
| M1 | `data/` | Data ingestion (prices, delivery, fundamentals, indices) | -- |
| M2 | `scanner/market_regime.py` | Bull/Neutral/Bear classification | -- |
| M3 | `scanner/sector_rotation.py` | Sector momentum ranking | 20 |
| M4 | `ranking/momentum_score.py` | Multi-timeframe momentum | 40 |
| M5 | `ranking/canslim_score.py` | CANSLIM fundamental filter | 25 |
| M6 | `ranking/accumulation_score.py` | Institutional accumulation | 15 |
| M7 | `scanner/trend_template.py` | Minervini 8-condition hard filter | 15 |
| M8 | `scanner/breakout_patterns.py` | VCP, base, resistance, volume breakout | 10 |
| M9 | `ranking/composite_score.py` | Composite score aggregation | **125** |
| M10 | `ranking/watchlist.py` | Generate + persist ranked watchlist | -- |
| M11 | `pipeline/runner.py` | Master pipeline orchestrator | -- |

## Scoring System

### Composite Score (max 125 points)

| Component | Range | Source |
|-----------|-------|--------|
| Momentum (scaled_score) | 0-40 | Multi-timeframe momentum with volatility scaling |
| Fundamental (CANSLIM) | 0-25 | EPS acceleration, revenue growth, D/E |
| Sector bonus | -5 to +20 | Top 3 sectors get +10, bottom 3 get -5 |
| Technical (trend template) | 0-15 | 8-condition Minervini filter |
| Accumulation | 0-15 | OBV +5, A/D ratio +4, institutional flow signals |
| Breakout | 0-10 | VCP, tight base, resistance breakout detection |

### Market Regime

5 levels: Strong Bull, Bull, Weak, Bear, Full Bear. Scored 0-6 from 6 signals plus a crash indicator. Controls max equity exposure, max positions, and risk per trade.

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `DB_TARGET` | No | `local` or `neon` -- controls SSL + pool settings |
| `APP_ENV` | No | `development` enables SQLAlchemy echo |
| `LOG_LEVEL` | No | loguru level, default INFO |
| `CORS_ORIGINS` | No | Comma-separated allowed origins for API |
| `SCREENER_USERID` | No | Screener.in premium account credentials |
| `SCREENER_PASSWORD` | No | Screener.in premium account credentials |
| `RESEND_API_KEY` | No | Resend email API key for alerts |
| `AWS_ACCESS_KEY_ID` | No | S3 parquet archive storage |

## Project Structure

```
src/momentum_edge/
  api/                  # FastAPI REST API
    routes/             # Endpoint handlers (watchlist, scores, regime, sectors, stocks)
  backtest/             # Backtesting engine, structured tests, walk-forward validation
  data/                 # Data ingestion modules (prices, delivery, fundamentals, screener, etc.)
  db/                   # SQLAlchemy models, session management
  engine/               # Signal generation, position sizing, exit rules
  notifications/        # Email alerts via Resend
  pipeline/             # Pipeline orchestrator + cron scheduling
  ranking/              # Scoring modules (momentum, CANSLIM, accumulation, composite, watchlist)
  scanner/              # Market regime, sector rotation, trend template, breakout patterns
  utils/                # Date utilities, logging, retry logic
```

## Daily Workflow

```bash
# After market close (~4:15 PM IST)
PYTHONPATH=src uv run python main.py run          # ingest + scan + watchlist
PYTHONPATH=src uv run python main.py watchlist     # view results
```

Or separately:

```bash
PYTHONPATH=src uv run python main.py ingest        # M1: data ingestion
PYTHONPATH=src uv run python main.py scan          # M2-M10: scan + score + watchlist
PYTHONPATH=src uv run python main.py watchlist     # view ranked output
```
