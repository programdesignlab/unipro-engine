# MomentumEdge — Frontend Integration Guide

## API Base URL

**Production:** `https://unipro-engine-production.up.railway.app`
**Local dev:** `http://localhost:8000`

No authentication required currently (JWT planned for Phase 2).

---

## Endpoints

### GET /health

```json
{"status": "ok", "version": "2.0"}
```

### GET /api/v1/watchlist

Today's ranked watchlist (max 20 stocks).

**Query params:**
- `date` (optional): `YYYY-MM-DD`, defaults to latest available

**Response:**
```json
[
  {
    "rank": 1,
    "symbol": "ANANDRATHI",
    "name": "Anand Rathi Wealth Limited",
    "composite_score": 122.5,
    "pattern_type": null,
    "regime": "Bear",
    "stop_loss_level": 2992.10,
    "sector_name": "Financial Services",
    "sector_rank": 1
  }
]
```

**Additional fields available (v7 watchlist table):**
- `tier` — 1 (Buy Now), 2 (Near Pivot), 3 (On Radar)
- `momentum_score` — percentile-based momentum with vol scaling
- `fundamental_bonus` — -5 to +20 bonus points
- `obv_bonus` — 0 or 5 (OBV accumulation signal)
- `adl_ratio` — 20-day accumulation/distribution ratio
- `delivery_trend` — display context only
- `inst_flow_signal` — FII/DII/bulk_deal signal source
- `inst_flow_positive` — boolean
- `entry_zone_low`, `entry_zone_high` — suggested entry range
- `suggested_size_pct` — position size as % of portfolio
- `vol_scalar` — volatility scaling factor applied
- `earnings_date` — next results date
- `earnings_flag` — true if results within 10 days

### GET /api/v1/scores/{symbol}

Score breakdown for a specific stock (latest date).

**Response:**
```json
{
  "id": 47,
  "stock_id": 56,
  "date": "2026-03-18",
  "momentum_score": 45.2,
  "fundamental_score": 8.0,
  "sector_score": 10.0,
  "technical_score": 12.7,
  "accumulation_score": 4.0,
  "breakout_score": 0.0,
  "composite_score": 79.9,
  "symbol": "RELIANCE",
  "name": "Reliance Industries Limited"
}
```

**Score components explained:**
| Component | Range | What it measures |
|-----------|-------|-----------------|
| `momentum_score` | 0-200 | Percentile-ranked 12-1m/6m/3m momentum with volatility scaling |
| `fundamental_score` | -5 to +20 | EPS acceleration (+8), growth (+5), D/E bonus/penalty |
| `sector_score` | -5, 0, or +10 | Top 3 sectors get +10, bottom 3 get -5 |
| `technical_score` | 0-15 | 8-condition Minervini trend template |
| `accumulation_score` | 0-11 | OBV (+5) + A/D ratio (+4) + institutional flow (+2) |
| `breakout_score` | 0-10 | VCP, tight base, or resistance breakout |
| `composite_score` | uncapped | Sum of all components |

### GET /api/v1/regime

Current market regime.

**Response:**
```json
{
  "regime": "Bear",
  "date": "2026-03-18"
}
```

**Regime levels:**
| Regime | Score | Max Equity | Max Positions | Risk/Trade |
|--------|-------|-----------|--------------|-----------|
| Strong Bull | 5.0-6.0 | 100% | 15 | 2.0% |
| Bull | 4.0-5.0 | 80% | 12 | 1.5% |
| Weak | 2.5-4.0 | 50% | 8 | 1.0% |
| Bear | 1.0-2.5 | 25% | 4 | 0.5% |
| Full Bear | 0-1.0 | 0% | 0 | Exit all |

**6 regime signals:**
1. Nifty close > 200-day MA
2. 200-day MA slope rising
3. Breadth (% stocks above 50MA)
4. New highs vs lows ratio
5. Nifty extension from 200MA
6. Nifty 12-1 month return positive

Plus crash indicator: if 2yr return < -20% AND 1m return > +10% → force Full Bear.

### GET /api/v1/sectors

Sector rotation with stock counts and average momentum.

**Response:**
```json
[
  {
    "id": 14,
    "sector_name": "Financial Services",
    "parent_sector": null,
    "stock_count": 85,
    "avg_momentum": 42.15
  }
]
```

### GET /api/v1/stocks

Stock universe with metadata.

**Query params:**
- `active` (optional): `true` to filter active stocks only

**Response:** Array of stock objects with all fields from `stocks` table.

**Key fields per stock:**
```json
{
  "id": 56,
  "symbol": "RELIANCE",
  "name": "Reliance Industries Limited",
  "sector": "Energy",
  "industry": "Oil & Gas Refining & Marketing",
  "market_cap": 1873444.11,
  "is_active": true,
  "is_asm": false,
  "is_esm": false,
  "is_financial": false,
  "promoter_holding_pct": 50.0,
  "fii_holding_pct": 19.09,
  "dii_holding_pct": 20.1,
  "is_fii_breached": false,
  "screener_export_id": 6598251
}
```

---

## Database Tables Available

### Core Data

| Table | Rows | Description |
|-------|------|-------------|
| `stocks` | 502 | Stock universe (500 active + 2 inactive) |
| `eod_prices` | 1M+ | Daily OHLCV + adj_close, 10yr history |
| `delivery_data` | 340K+ | Daily delivery qty/pct, 2yr history |
| `fundamentals` | 5K | Quarterly EPS, revenue, D/E from Screener.in |
| `shareholding_pattern` | 5.7K | Quarterly promoter/FII/DII/public % |
| `corporate_actions` | 247 | Splits + bonuses for adj_close calculation |

### Market Data

| Table | Description |
|-------|-------------|
| `fii_dii_data` | Daily FII/DII buy/sell/net (aggregate) |
| `bulk_deals` | Block and bulk deal records |
| `sector_data` | 12 sectors with classification |

### Pipeline Output (updated daily)

| Table | Description |
|-------|-------------|
| `indicators` | 25+ technical indicators per stock per day |
| `scores` | Composite + component scores per stock per day |
| `watchlist` | Ranked watchlist (max 20 stocks) |
| `signals` | Trading signals with lifecycle (Pending/Confirmed/Failed) |

### Backtesting

| Table | Description |
|-------|-------------|
| `backtest_results` | Test results with all metrics |
| `walkforward_results` | Walk-forward validation fold results |
| `performance_log` | Individual trade records |

---

## Data Update Schedule

| Data | Frequency | Time (IST) | Trigger |
|------|-----------|------------|---------|
| OHLCV + delivery | Daily | 4:15 PM | Cron pipeline |
| Indicators + scores | Daily | 4:15 PM | Cron pipeline |
| Watchlist | Daily | 4:15 PM | Cron pipeline |
| FII/DII | Daily | 4:15 PM | Cron pipeline |
| Bulk/block deals | Daily | 4:15 PM | Cron pipeline |
| ASM/ESM flags | Daily | 4:15 PM | Cron pipeline |
| Fundamentals | Quarterly | Manual | `sync-screener` command |
| Shareholding | Quarterly | Manual | `sync-screener` command |
| Corporate actions | As announced | Manual | `sync-corporate-actions` |

---

## Scoring System Detail

### Composite Score = sum of all components (uncapped)

**Momentum (scaled_score):** 0-200 range
- Percentile-rank 12-1m (40%), 6m (35%), 3m (25%) momentum returns
- Multiply by volatility scalar: `min(20% / annualized_vol, 2.0)`
- Low-volatility stocks get boosted, high-vol stocks get dampened

**Fundamental Bonus:** -5 to +20
- +8 EPS acceleration (3 quarters of accelerating YoY growth)
- +5 EPS growth >= 15% (latest quarter)
- +2 EPS growth >= 0%
- +4 Analyst upward revision (if available)
- +3/+2/+1 D/E ratio < 1.0/1.5/2.0 (skip for banks/NBFCs)
- -2 D/E > 3.0

**Sector Bonus:** -5, 0, or +10
- +10 if stock in top 3 sectors by momentum
- -5 if in bottom 3 sectors
- 0 otherwise

**Technical Score:** 0-15
- Based on 8-condition Minervini trend template
- All conditions use adj_close (split-adjusted)

**Accumulation Score:** 0-11
- +5 OBV slope rising during base period
- +4 A/D ratio >= 0.60 (up-volume dominance)
- +2 Smart institutional flow positive

**Breakout Score:** 0-10
- VCP detection with 3+ contractions, declining volume
- OBV divergence detection
- Circuit breaker exclusion (upper circuit = not genuine VCP)

### Signal Tiers

| Tier | Meaning | Criteria |
|------|---------|----------|
| 1 | Buy Now | Confirmed breakout + Bull regime + high score |
| 2 | Near Pivot | Within 3% of pivot + score > 65 |
| 3 | On Radar | Eligible + score > 55, OR earnings within 10 days |

### Smart Institutional Flow

Routes signal source based on each stock's ownership structure:
- **Promoter < 65%:** Use FII + DII combined flow
- **Promoter 65-75%:** Use DII only (FII has limited room)
- **Promoter > 75% or FII-capped:** Use bulk/block deal data

---

## UI Pages Suggested

### 1. Dashboard
- Market regime indicator (Bull/Bear/Weak with color coding)
- Crash warning alert if active
- Top 10 watchlist stocks with scores
- Sector heatmap (avg momentum by sector)
- FII/DII daily net flow bar

### 2. Watchlist
- Full ranked watchlist with all score components
- Pattern type badges (VCP, TightBase, Breakout)
- Entry zone + stop loss levels
- Tier badges (1/2/3)
- Earnings flag warning icon
- Filter by: sector, pattern, tier, regime

### 3. Stock Detail
- Price chart with MA50/150/200 overlays
- Score breakdown radar/bar chart
- Fundamental quarters table (EPS, revenue, margins)
- Shareholding pie chart (promoter/FII/DII/public)
- Shareholding trend over quarters
- Signal history for this stock
- Delivery % trend (display only)

### 4. Market Regime
- 6 signal breakdown with current values
- Regime history chart over time
- Breadth indicator (% above 50MA)
- Nifty vs 200MA chart

### 5. Sector Analysis
- Sector rotation ranking table
- Stock count per sector
- Average momentum per sector
- Top stocks per sector

### 6. Screener/Universe
- All 500 stocks filterable by:
  - Market cap range
  - Sector
  - Is financial / ASM / ESM
  - Promoter holding range
  - FII/DII holding
  - Momentum rank
- Column sort on any metric

### 7. Backtest Results (if exposed)
- Test comparison table
- Equity curve chart
- Trade log with entry/exit dates
- Performance metrics dashboard
- Walk-forward fold results

---

## CORS

The API allows cross-origin requests from origins configured in `CORS_ORIGINS` env var (comma-separated). For local React dev, add `http://localhost:3000`.

## Rate Limits

No rate limiting currently. The API is lightweight — all queries hit PostgreSQL (Neon) directly.

## Error Handling

All endpoints return JSON. On error:
```json
{"detail": "Error description"}
```
HTTP 500 for server errors, 404 for not found.
