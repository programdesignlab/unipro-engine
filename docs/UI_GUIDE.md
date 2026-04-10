# MomentumEdge — Frontend Integration Guide

## API Base URL

- **Production:** `https://api.uniproadvisory.com`
- **Local dev:** `http://localhost:8000`

All `/api/v1/*` routes require a valid JWT (Neon Auth / EdDSA).

---

## Endpoints

### Health

```
GET /health → {"status": "ok", "version": "2.0"}
```

### Watchlist

```
GET /api/v1/watchlist?date=YYYY-MM-DD
```

Response: array of ranked stocks with scores, pattern types, entry zones, stop losses.

| Field | Type | Description |
|-------|------|-------------|
| `rank` | int | Position in ranked list |
| `symbol` | string | NSE symbol |
| `composite_score` | float | Total score (uncapped) |
| `pattern_type` | string | VCP / Base / Breakout / null |
| `regime` | string | Market regime at scan time |
| `stop_loss_level` | float | Lowest low of last 20 days |
| `sector_name` | string | NSE sector |
| `sector_rank` | int | Sector momentum rank |
| `tier` | int | 1 (Buy Now) / 2 (Near Pivot) / 3 (On Radar) |
| `momentum_score` | float | Percentile momentum with vol scaling |
| `fundamental_bonus` | int | -20 to +30 |
| `entry_zone_low` | float | Lower bound of entry range |
| `entry_zone_high` | float | Upper bound of entry range |
| `vol_scalar` | float | Volatility scaling factor |
| `earnings_date` | date | Next results date |
| `earnings_flag` | bool | True if results within 10 days |

### Scores

```
GET /api/v1/scores/{symbol}
```

Score breakdown for a stock. All 6 components + composite + strategy_hash.

| Component | Range | Description |
|-----------|-------|-------------|
| `momentum_score` | 0-200 | Percentile-ranked multi-timeframe momentum |
| `fundamental_score` | -20 to +30 | 14 bonuses + 7 penalties |
| `sector_score` | -5 to +10 | Sector momentum rank bonus/penalty |
| `technical_score` | 0-15 | Minervini trend template |
| `accumulation_score` | 0-11 | OBV + A/D + institutional flow |
| `breakout_score` | 0-10 | VCP, tight base, or breakout |
| `composite_score` | uncapped | Sum of all components |
| `strategy_hash` | string | Config version tag |

### Regime

```
GET /api/v1/regime          → {"regime": "Weak", "date": "2026-04-10"}
GET /api/v1/regime/signals  → 6-signal breakdown with individual values
```

**Regime levels:** Strong Bull / Bull / Weak / Bear / Full Bear

| Regime | Equity | Positions | Risk/Trade |
|--------|--------|-----------|------------|
| Strong Bull | 100% | 15 | 2.0% |
| Bull | 80% | 12 | 1.5% |
| Weak | 50% | 8 | 1.0% |
| Bear | 25% | 4 | 0.5% |
| Full Bear | 0% | 0 | Exit all |

### Strategy

```
GET /api/v1/strategy/info   → name, version, hash, feature flags
GET /api/v1/strategy/params → full YAML config as JSON (read-only)
```

### Exclusions (Audit Trail)

```
GET /api/v1/exclusions?date=YYYY-MM-DD&symbol=RELIANCE&limit=50
```

Returns why stocks were excluded from the universe with filter name, reason, and whether data was missing.

### Turnaround Watch

```
GET /api/v1/turnaround-watch?active_only=true
```

Stocks detected as potential turnarounds (EPS improving but hard block still active).

| Field | Description |
|-------|-------------|
| `symbol` | Stock symbol |
| `detected_date` | When turnaround was first detected |
| `eps_trend` | Last 8 quarters EPS values |
| `revenue_growth_yoy` | Latest revenue growth % |
| `suppressed` | True if suppressed (pledge/SEBI/OCF issue) |
| `suppression_reason` | Why suppressed |

### Other Endpoints

```
GET /api/v1/sectors                → Sector rotation ranking
GET /api/v1/stocks?active=true     → Stock universe with metadata
GET /api/v1/stock/{symbol}/detail  → OHLCV + fundamentals + scores
GET /api/v1/signals/{symbol}       → Signal history for a stock
GET /api/v1/fii-dii                → Daily FII/DII flows
GET /api/v1/shareholding/{symbol}  → Quarterly shareholding pattern
```

---

## UI Pages

### 1. Dashboard
- Market regime indicator with color coding (green/yellow/red)
- Fast crash warning alert banner (if active)
- Top 10 watchlist with scores and pattern badges
- Sector heatmap (momentum by sector)
- FII/DII daily net flow bar
- Strategy version + hash display

### 2. Watchlist
- Full ranked list with all score components
- Pattern badges: VCP / TightBase / Breakout
- Tier badges: 1 (green) / 2 (amber) / 3 (grey)
- Entry zone + stop loss levels
- Earnings flag warning icon
- Filters: sector, pattern, tier, regime

### 3. Stock Detail
- Price chart with MA50/150/200 overlays
- Score breakdown bar chart (6 components)
- Fundamental quarters table
- Shareholding pie chart + trend
- Signal history timeline
- Monster score (if applicable)
- Turnaround watch status (if applicable)

### 4. Regime Monitor
- 6-signal breakdown with gauges
- Regime history chart
- Breadth indicator (% above 50MA)
- Fast crash detector status
- Bull entry protocol phase (if recovering from Bear)

### 5. Exclusion Audit
- Table of filtered stocks with reasons
- Filter by date, symbol, block name
- Data-missing vs rule-based exclusion distinction

### 6. Turnaround Watch
- Active candidates with EPS trend sparklines
- Suppressed entries (greyed out) with reasons
- Days until EPS block expected to clear

---

## CORS

API allows cross-origin requests from `CORS_ORIGINS` env var (comma-separated). For local React dev, set `http://localhost:3000`.

## Authentication

All `/api/v1/*` routes require a Bearer JWT token. The token is verified against Neon Auth JWKS (EdDSA algorithm). Include in requests:

```
Authorization: Bearer <jwt_token>
```

## Data Update Schedule

| Data | Frequency | Time (IST) |
|------|-----------|------------|
| OHLCV + delivery | Daily | 4:30 PM |
| Indicators + scores + watchlist | Daily | 4:30 PM |
| FII/DII + bulk deals + ASM/ESM | Daily | 4:30 PM |
| Fundamentals + shareholding | Quarterly | Manual sync |
| Corporate actions | As announced | Manual sync |
