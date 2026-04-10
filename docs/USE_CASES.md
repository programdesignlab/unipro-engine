# MomentumEdge — Use Cases

## UC-01: Daily Stock Scanning Pipeline

**Actor:** Cron scheduler (Railway, 4:30 PM IST daily, Mon-Fri)

**Flow:**
1. Ingest daily data: OHLCV prices, delivery stats, FII/DII flows, bulk deals, ASM/ESM flags
2. Compute 25+ technical indicators for all 500 stocks
3. Detect market regime (6 signals → 5 levels)
4. Check fast crash detector (5-day rolling Nifty decline > 8%)
5. Rank sectors by momentum
6. Filter universe through 8 hard blocks
7. Score each eligible stock across 6 dimensions
8. Generate ranked watchlist
9. Process signal lifecycle (Pending → Confirmed/Failed/Expired)
10. Log pipeline steps with timing

**Output:** Ranked watchlist with composite scores, pattern types, entry zones, stop losses. All tagged with strategy hash.

---

## UC-02: Universe Filtering (8 Hard Blocks)

**Purpose:** Remove junk stocks before scoring. Fail-closed on critical missing data.

| Block | Condition | Data Source |
|-------|-----------|-------------|
| Market cap band | Rs 1,000-30,000 crore | Stock master |
| Liquidity | Avg daily traded value >= Rs 15 crore | EOD prices |
| Surveillance | Not under ASM/ESM | NSE surveillance list |
| EPS junk | Positive EPS in 2+ of last 4 quarters | Screener fundamentals |
| OCF quality | OCF not negative in 3+ of 4 quarters | Screener fundamentals |
| Promoter pledge | Pledge < 20% (operational) or 50% (infra) | Shareholding data |
| SEBI fine | No price manipulation fine in 24 months | Stock flags |
| IPO age | Listed >= 200 trading days | Listing date / price count |

All thresholds configurable via `strategies/momentum_edge.yaml`.

---

## UC-03: Composite Scoring (6 Dimensions)

**Purpose:** Rank eligible stocks by multi-factor evidence-based score.

| Module | Weight | Range | What It Measures |
|--------|--------|-------|------------------|
| Momentum | 0.35 | 0-200 | Percentile-ranked 12-1m/6m/3m returns with volatility scaling |
| Fundamental | 0.20 | -20 to +30 | 14 bonuses + 7 penalties (EPS, revenue, promoter, D/E, OCF) |
| Accumulation | 0.15 | 0-11 | OBV slope + A/D ratio + smart institutional flow |
| Sector | 0.10 | -5 to +10 | Sector momentum rank (top 3 = +10, bottom 3 = -5) |
| Technical | 0.12 | 0-15 | 8-condition Minervini trend template |
| Breakout | 0.08 | 0-10 | VCP + tight base + resistance breakout with OBV |

Composite = additive sum (uncapped). Strategy hash tagged on every score row.

---

## UC-04: Market Regime Detection

**6 signals (0-6 total score):**
1. Nifty close > 200-day MA
2. 200-day MA slope rising
3. Breadth: % stocks above 50-day MA
4. New 52-week highs vs lows ratio
5. Nifty extension from 200MA
6. 12-minus-1-month Nifty return

**Crash indicator (Dierkes & Krupski 2022):** 2yr return < -20% AND 1m return > +10% → force Full Bear.

**Stability rule:** Regime changes only after 3 consecutive days at new level.

| Regime | Score | Equity | Positions | Risk/Trade | Heat |
|--------|-------|--------|-----------|------------|------|
| Strong Bull | 5.0-6.0 | 100% | 15 | 2.0% | 6.0% |
| Bull | 4.0-5.0 | 80% | 12 | 1.5% | 5.0% |
| Weak | 2.5-4.0 | 50% | 8 | 1.0% | 4.0% |
| Bear | 1.0-2.5 | 25% | 4 | 0.5% | 2.0% |
| Full Bear | 0.0-1.0 | 0% | 0 | 0.0% | 0.0% |

---

## UC-05: 4-Phase Exit Engine

**Purpose:** Gain-based exit rules that loosen as a position proves itself.

| Phase | Gain Range | Primary Rule |
|-------|-----------|--------------|
| Prove It | 0-25% | 8% fixed stop from entry |
| Let It Run | 25-100% | 20% trail from 10-week high |
| Working Compounder | 100-200% | 15% trail from 10-week high |
| Monster Run | 200%+ | 50MA primary, 12% trail on core, partial exits at highs |

**3 validation layers:**
- Trend integrity: higher highs/lows intact → suppress MA weakness exit
- Volume direction: low vol on down days = hold; high vol = instant 25% exit
- ATR compression: suppress time stop if ATR compressed vs entry

**5-layer portfolio cascade (E1-E5):**
- E1: Climax detection (80%+ gain + 30% surge in 15d)
- E2: Distribution days (index down on higher volume count)
- E3: A/D divergence (index new high + A/D lower high)
- E4: New highs collapse (Nifty500 52w highs dropping)
- E5: Tiered trailing (per-position phase-dependent)

---

## UC-06: Fast Crash Detector

**Purpose:** Independent of regime stability rule (which takes 3 days).

- **Trigger:** Nifty declines > 8% in any rolling 5-trading-day window
- **Response:** Sell 50% of every open position; block all new entries
- **Reset:** No 5-day window in last 10 days shows > 8% decline
- **Interaction:** Halves monster positions too. Monster override stays active — Phase 4 rules resume after reset.

---

## UC-07: Monster Stock Detection

**Based on:** Bessembinder 2018 (top 4% of stocks drive all net market wealth).

7 criteria scoring 0-100:
| Criterion | Points |
|-----------|--------|
| RS rank >= 90th percentile | +25 |
| 3+ prior accumulation bases | +20 |
| 70%+ weekly closes positive | +20 |
| Sector rank = #1 | +15 |
| EPS acceleration 4+ quarters | +10 |
| Base depth contracting | +10 |
| Sector outperformance >= 2x | +10 |

**Activation:** Score >= 80 AND gain >= 40% → override to Monster Run exit phase.

---

## UC-08: Position Sizing

**Base:** Risk per trade from regime classification.

**3 adjustment layers (multiplicative):**
1. Beta > 2.5 → 40% size reduction
2. Thin float (promoter > 75%, non-PSU) → 40% reduction
3. Correlation > 0.85 with existing holding → 50% reduction; > 0.70 → 25%

**Constraints:**
- Position floor: 2% of portfolio
- Position ceiling: 20% of portfolio
- Sector concentration: max 30%
- Portfolio heat: regime-dependent (6%/5%/4%/2%/0%)

---

## UC-09: Bull Market Entry Protocol

**Purpose:** Prevent capital deployment into failed bear rallies.

| Phase | Trigger | Capital Deploy |
|-------|---------|---------------|
| B1 Capitulation | Panic volume > 2x avg + A/D higher low | 0% (watch) |
| B2 Breadth Thrust | Single day 90%+ advancing volume | 25% |
| B3 A/D Confirmation | A/D line higher high than capitulation | 50% |
| B4 New Highs Expand | 52w highs > 100/week for 2+ weeks | Full regime % |

Phases only advance forward.

---

## UC-10: Turnaround Watch

**Purpose:** Detect business turnarounds 1-3 quarters before EPS block clears.

**Conditions (all must be true):**
1. EPS negative in >= 2 of last 8 quarters
2. EPS improving monotonically for last 4 quarters
3. Most recent quarter EPS > 0
4. Revenue growing > 10% YoY
5. EPS hard block still active (< 2 of 4 quarters positive)

**Suppression:** Pledge > threshold, SEBI fine, 3+ business pivots, OCF negative 3+/4 quarters.

---

## UC-11: Signal Lifecycle

**States:** Pending → Confirmed / Failed / Expired

**Day 1:** Breakout detected → signal created as Pending
**Day 2+:**
- Open > pivot + 3% → Expired (gap too large)
- Close > pivot → Confirmed
- Close <= pivot → Failed

**Tiers:**
| Tier | Criteria |
|------|----------|
| 1 (Buy Now) | Breakout confirmed + Bull regime + score >= 75 |
| 2 (Near Pivot) | Score >= 65 |
| 3 (On Radar) | Score >= 55, or earnings within 10 days |

---

## UC-12: Backtesting

**Strategy-driven:** Reads all params from strategy YAML.
- Transaction costs: configurable slippage, brokerage, STT, exchange fees
- v16 phase-based exits or v7 flat rules (configurable)
- Parameter sweep: combinatorial grid over FREE params, ranked by Sharpe
- Walk-forward validation with expanding windows

---

## UC-13: REST API

14 authenticated endpoints serving watchlist, scores, regime, sectors, stocks, signals, strategy info, exclusions, and turnaround watch to the frontend React app.
