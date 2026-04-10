# MomentumEdge

Automated NSE stock scanning and ranking system with configurable strategy engine for Indian equities.

## What it does

- Scans **Nifty 500** stocks daily using multi-timeframe momentum + volatility scaling
- **YAML-driven strategy** — all parameters, scoring weights, exit rules in one config file
- **8 hard block filters** for universe screening (market cap, liquidity, ASM, EPS, OCF, pledge, SEBI, IPO age)
- **6-dimension scoring:** momentum, fundamentals (14 bonuses + 7 penalties), accumulation, sector rotation, trend template, breakout patterns
- **4-phase exit engine** (prove_it → let_it_run → working_compounder → monster_run) with 5-layer portfolio cascade
- **Fast crash detector** (independent of regime stability rule)
- **Monster stock detection** (7 criteria, based on Bessembinder 2018)
- **Bull market entry protocol** (4-phase structured re-entry after Bear)
- **6-signal market regime** with crash indicator (Dierkes & Krupski 2022)
- **Strategy-driven backtesting** with parameter sweep support
- **14 REST API endpoints** for frontend integration

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12, `uv` package manager |
| Strategy | YAML + Pydantic validation (36 models) |
| Database | PostgreSQL — Neon (prod), local (dev) |
| API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 + Alembic |
| Compute | Railway (cron + web service) |
| Data | NSE bulk CSV, yfinance, Screener.in |
| Email | Resend API |

## Quick Start

```bash
uv sync
cp .env.example .env                                     # edit with your credentials
PYTHONPATH=src uv run python -m alembic upgrade head      # apply migrations
PYTHONPATH=src uv run python main.py sync-universe --index nifty500
PYTHONPATH=src uv run python main.py bootstrap
PYTHONPATH=src uv run python main.py sync-screener
PYTHONPATH=src uv run python main.py run                  # full pipeline
PYTHONPATH=src uv run python main.py watchlist             # view results
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `status` | DB connection + row counts |
| `sync-universe --index nifty500` | Sync stock universe |
| `bootstrap` | Bootstrap 10yr OHLCV prices |
| `bootstrap-delivery-bulk` | Bootstrap 2yr delivery data |
| `sync-screener` | Sync fundamentals from Screener.in |
| `run [--date] [--strategy path]` | Full pipeline (strategy-driven) |
| `watchlist [--date]` | View ranked watchlist |
| `backtest` | Run backtest from strategy YAML |

## API Endpoints

Production: `https://api.uniproadvisory.com`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/watchlist` | Ranked watchlist |
| GET | `/api/v1/scores/{symbol}` | Score breakdown |
| GET | `/api/v1/regime` | Market regime |
| GET | `/api/v1/regime/signals` | 6-signal breakdown |
| GET | `/api/v1/sectors` | Sector rankings |
| GET | `/api/v1/stocks` | Stock universe |
| GET | `/api/v1/stock/{symbol}/detail` | Stock detail |
| GET | `/api/v1/signals/{symbol}` | Signal history |
| GET | `/api/v1/strategy/info` | Strategy metadata + hash |
| GET | `/api/v1/strategy/params` | Full strategy config |
| GET | `/api/v1/exclusions` | Filter exclusion audit trail |
| GET | `/api/v1/turnaround-watch` | Turnaround candidates |
| GET | `/api/v1/fii-dii` | FII/DII flows |

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System overview, source structure, database schema |
| [Use Cases](docs/USE_CASES.md) | 13 use cases covering all engine features |
| [Implementation](docs/IMPLEMENTATION.md) | Code guide, adding modules, CLI, config |
| [UI Guide](docs/UI_GUIDE.md) | Frontend integration, endpoints, UI page specs |

## Environment Variables

See `.env.example` for the full list. Key variables: `DATABASE_URL`, `SCREENER_USERID`, `SCREENER_PASSWORD`.
