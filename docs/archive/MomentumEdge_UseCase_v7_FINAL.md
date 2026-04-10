# MomentumEdge — Final Use Case Document v7.0
## Production-Grade NSE Momentum Platform
### Evidence-Based | 10-Year Backtest | All Flaws Fixed

**Version:** 7.0
**Date:** March 2026
**Status:** Final — Implementation Ready
**Backtest:** January 2015 – December 2024 (10 years, 8 market cycles)

**Evidence base:**
- Jegadeesh & Titman 1993 — pure momentum, no fundamental filters needed
- Baltussen et al. 2026 — 150 years, 46 countries, momentum works everywhere
- NSE Nifty200 Momentum 30 Index — 19.06% CAGR, zero fundamental filter
- Novy-Marx 2015 — price momentum IS fundamental momentum
- Barroso & Santa-Clara 2015 — volatility scaling doubles Sharpe ratio
- Dierkes & Krupski 2022 — crash indicator reduces tail risk
- Granville 1963 — OBV: volume precedes price, 60-year track record
- He & Narayanamoorthy 2017 — earnings acceleration predicts returns
- AQR QMJ factor — quality as score alongside momentum, not filter

**Changes from v6 → v7:**
1. Delivery % removed from scoring entirely (zero evidence, operator contaminated)
2. OBV slope during base added (+5 bonus) — replaces delivery, globally validated
3. FII sector flow added (+2 bonus) — direct institutional proxy
4. Earnings date awareness added — critical India-specific safety rule
5. Max entry price rule added (3% above pivot) — prevents chasing gaps
6. Rolling-window walk-forward added — stricter overfit test
7. OBV scope fixed — calculate from base start date only, not inception

---

## 1. Non-Negotiable Principles

```
ARCHITECTURE:
- 3 fully separated engines: Alpha / Execution / Risk — never mix them
- Momentum is the ONLY stock selection signal
- Execution engine times entries only — does not select stocks
- Risk engine controls allocation only — no stock opinions

DATA:
- ALL calculations on adj_close — never raw close
- ALL fundamentals filtered by reporting_date — never period_end_date
- Survivorship bias: include all delisted stocks in backtest universe
- Delivery %: stored and displayed only — zero scoring, zero filtering

ACCUMULATION SIGNALS (in order of evidence):
1. Breakout volume ratio >= 1.5x 50d avg (hard entry condition, primary)
2. OBV slope rising during base period (bonus +5, globally validated)
3. A/D ratio >= 0.60 over 20 days (bonus +4, Minervini method)
4. Smart institutional flow — FII/DII/bulk deal based on promoter holding (bonus +2)
   Rule: promoter <65% → FII+DII | promoter 65-75% → DII only | >75% or defence/PSU or breach list → bulk deals only
5. Volume contraction across VCP contractions (hard VCP rule)
6. Delivery % rising (displayed as context only — NOT scored)

FUNDAMENTALS:
- 4 hard filters only: positive EPS 2/4 qtrs, not ASM/ESM,
  market cap band, minimum liquidity
- Everything else = bonus scores (never eliminates stocks)
- EPS acceleration = highest evidence fundamental signal (+8 bonus)

SAFETY:
- Earnings due within 10 days → auto-downgrade to Tier 3
- Next-day open > pivot + 3% → signal expires, do not enter
- Nothing goes live without passing all 12 backtest gates
```

---

## 2. System Architecture

```
NSE UNIVERSE
Stocks | Market cap 2,000–30,000 crore | Active | ~300–400 stocks
        |
        | 4 HARD FILTERS (junk removal only):
        | 1. Positive EPS in 2 of last 4 reported quarters
        | 2. Not under ASM / ESM surveillance
        | 3. Market cap 2,000–30,000 crore
        | 4. Average daily traded value >= Rs.15 crore
        |
        v
  ┌─────────────────────────────────────────────┐
  │  ENGINE A — ALPHA ENGINE                    │
  │  Multi-timeframe momentum (12-1/6m/3m)      │
  │  Volatility scaling (Barroso & Santa-Clara) │
  │  RS rank filter (top 30% vs Nifty 50)       │
  │  Momentum quality >= 0.55                   │
  │  Fundamental bonus scores (NOT hard filter) │
  │  Sector bonus / penalty                     │
  └─────────────────────────────────────────────┘
        |
        v
  ELIGIBLE UNIVERSE (top 15-20%, ~60-80 stocks)
        |
        v
  ┌─────────────────────────────────────────────┐
  │  ENGINE B — EXECUTION ENGINE                │
  │  8-condition Minervini trend template       │
  │  VCP / Tight base / Breakout detection      │
  │  OBV slope check during base                │
  │  False breakout filter (2-day confirmation) │
  │  Entry rules: vol 1.5x, circuit, close pos  │
  │  Max entry: open > pivot+3% → expire        │
  │  Earnings safety: due <10 days → Tier 3     │
  │  Exit: tiered trailing + time + regime      │
  └─────────────────────────────────────────────┘
        |
        v
  SIGNALS (Tier 1 / 2 / 3) with sizes
        |
  ┌─────────────────────────────────────────────┐
  │  ENGINE C — RISK ENGINE                     │
  │  6-signal regime score                      │
  │  Momentum crash indicator                   │
  │  Portfolio volatility scaling               │
  │  2% risk rule position sizing               │
  │  Max entry 3% above pivot                   │
  │  Portfolio heat monitor (max 6%)            │
  │  Sector concentration (max 30%)             │
  │  Drawdown circuit breaker                   │
  └─────────────────────────────────────────────┘
        |
        v
  FINAL WATCHLIST (max 20 stocks, fully sized)
        |
        v
  BACKTEST 10yr → WALK-FORWARD → PAPER TRADE → LIVE
```

---

## 3. Data Sources

### 3.1 Price Data — NSE Archive (Primary)
```
URL: archive.nseindia.com/content/historical/EQUITIES/{YEAR}/{MON}/
File: cm{DD}{MON}{YYYY}bhav.csv.zip
Coverage: Free, official, 1994–present
Fields: SYMBOL, OPEN, HIGH, LOW, CLOSE, TOTTRDQTY, TOTTRDVAL, ISIN
Store: raw close AND adj_close separately
```

### 3.2 Delivery Data — NSE Archive (Store Only)
```
URL: archives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv
Fields: SYMBOL, QUANTITY_TRADED, DELIVERABLE_QTY, PERCENT_DELI_QTY_TO_TRADED_QTY
Store: delivery_qty, delivery_pct in price_data table
Use: Display in dashboard as context only
Score: ZERO — removed from all scoring and filtering
Reason: No academic evidence. Operator-contaminated in mid-caps.
        Replaced by OBV (Granville 1963, 60yr evidence) and smart institutional flow data.
```

### 3.3 Corporate Actions — NSE API (Critical)
```
URL: nseindia.com/api/corporates-corporateActions
     ?index=equities&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY
Fields: symbol, exDate, purpose (split/bonus/rights), ratio
Use: Calculate cumulative adj_factor → populate adj_close backwards
Rule: Every price calculation uses adj_close — never raw close
```

### 3.4 Fundamentals — Screener.in API
```
Cost: ~Rs.5,000/year
Critical fields:
  reporting_date    — when results announced (ALWAYS filter by this)
  period_end_date   — quarter end (stored but NEVER used as filter date)
  eps               — earnings per share
  eps_growth_yoy    — vs same quarter last year (NOT sequential)
  expected_result_date — upcoming results date (NEW — for safety rule)
  is_financial      — skip D/E score for banks/NBFCs
```

### 3.5 Institutional Flow Data — NSE Daily (Updated)
```
Source 1 — FII/DII aggregate (daily):
URL: nseindia.com/api/fiidiiTradeReact
Fields: date, fii_net_buy_cr, dii_net_buy_cr, sector breakdown
Use: Selective — only where FII can actually buy (see smart signal logic below)

Source 2 — Shareholding pattern (quarterly):
URL: Screener.in API or BSE shareholding XML
Fields: promoter_holding_pct, fii_holding_pct, dii_holding_pct, public_holding_pct
Use: Determines which institutional signal is reliable for each stock
     Update quarterly when companies file shareholding with exchanges

Source 3 — NSE breach/caution list (daily):
URL: nseindia.com/market-data/securities-available-for-trading (FII limits)
Fields: symbol, fii_limit_pct, current_fii_holding_pct, is_breached, is_cautioned
Use: If stock on breach list → FII buying is legally blocked → skip FII signal

Source 4 — Bulk/block deals (daily):
URL: nseindia.com/market-data/block-deal
Fields: date, symbol, client_name, deal_type, quantity, price, value_cr
Use: For high-promoter or FII-capped stocks — a known MF/insurance bulk buy
     is stronger institutional signal than aggregate FII sector flow

Smart institutional flow logic (applied per stock):
- promoter_pct < 65% AND not on breach list AND not FII-capped sector
  → Use FII + DII combined net flow (+2 bonus if net buyer)
- promoter_pct 65–75% OR on caution list
  → Use DII net flow only (+2 bonus if DII net buyer)
- promoter_pct > 75% OR defence/PSU sector OR on breach list
  → Use bulk deal data only (+2 bonus if known institution in bulk buy)
```

### 3.6 Delisted Stocks — Required for Backtest
```
NSE archive contains bhav data for delisted stocks up to last trading date.
Must include all stocks that were in 2,000–30,000 crore band 2015–2024
even if later delisted, suspended, or merged.
Ignoring delisted stocks overstates returns by 30–50%.
```

---

## 4. Use Cases

---

### UC-01: Daily Data Ingestion

**Trigger:** 4:15 PM IST every NSE trading day
**Postcondition:** Database updated with today's price, delivery, FII data.

**Flow:**
1. Check NSE holiday calendar — if holiday, log skip and exit
2. Download bhav copy → parse EQ series stocks
3. Download delivery bhav copy → delivery_qty, delivery_pct
4. Download FII/DII net activity
5. Check corporate actions → apply adj_factor if new action
6. Run validation gate:
   - >2% stocks missing → halt and alert admin
   - Single-day move >25% without corporate action → flag
   - 3+ consecutive zero volume days → exclude
   - Bhav copy date ≠ today → halt
7. Write raw close and adj_close to `price_data`
8. Write FII data to `fii_dii_data`
9. Log success → trigger UC-02

**Backtest verification:**
- Verify adj_close on 10 known split/bonus events manually
- Verify delivery data stored correctly (displayed only, not scored)

---

### UC-02: Indicator Calculation

**Postcondition:** All indicators calculated on adj_close for universe stocks.

```python
def calculate_indicators(symbol, as_of_date, price_df):
    p = price_df[price_df['symbol']==symbol]['adj_close'].sort_index()

    # Moving averages — all on adj_close
    ma50  = p.rolling(50).mean().iloc[-1]
    ma150 = p.rolling(150).mean().iloc[-1]
    ma200 = p.rolling(200).mean().iloc[-1]
    ma200_slope = ma200 - p.rolling(200).mean().iloc[-21]

    # Momentum returns — all on adj_close
    mom_3m   = (p.iloc[-1] / p.iloc[-63])  - 1
    mom_6m   = (p.iloc[-1] / p.iloc[-126]) - 1
    mom_12_1 = (p.iloc[-21] / p.iloc[-252]) - 1

    # Volatility scaling (Barroso & Santa-Clara 2015)
    daily_ret     = p.pct_change()
    mom_vol_20d   = daily_ret.rolling(20).std().iloc[-1]
    vol_annualised = mom_vol_20d * (252**0.5)
    vol_scalar    = min(0.20 / vol_annualised, 2.0) if vol_annualised > 0 else 1.0

    # Momentum quality (smooth uptrend filter)
    weekly       = p.resample('W').last().pct_change()
    mom_quality  = (weekly.tail(26) > 0).sum() / 26

    # OBV — calculated on full history (slope extracted per-base in UC-06)
    v    = price_df[price_df['symbol']==symbol]['volume'].sort_index()
    sign = p.diff().apply(lambda x: 1 if x>0 else (-1 if x<0 else 0))
    obv  = (sign * v).cumsum().iloc[-1]
    # OBV slope during base calculated separately in VCP detection

    # A/D ratio (Minervini accumulation/distribution days)
    last20   = price_df[price_df['symbol']==symbol].tail(20)
    up_vol   = last20[last20['adj_close']>last20['adj_close'].shift(1)]['volume'].sum()
    dn_vol   = last20[last20['adj_close']<last20['adj_close'].shift(1)]['volume'].sum()
    adl_ratio = up_vol/(up_vol+dn_vol) if (up_vol+dn_vol)>0 else 0.5

    # Volume ratios
    vol_ratio_20 = v.iloc[-1] / v.rolling(20).mean().iloc[-1]
    vol_ratio_50 = v.iloc[-1] / v.rolling(50).mean().iloc[-1]

    # 52-week metrics
    week52_high  = p.tail(252).max()
    week52_low   = p.tail(252).min()
    pct_from_high = (p.iloc[-1] / week52_high) - 1

    # Delivery trend (stored, displayed, NOT scored)
    delivery = price_df[price_df['symbol']==symbol]['delivery_pct']
    delivery_trend = delivery.tail(10).mean() - delivery.tail(20).head(10).mean()
    # delivery_trend stored for display only — never used in scoring

    return {
        'ma50':ma50,'ma150':ma150,'ma200':ma200,'ma200_slope':ma200_slope,
        'mom_3m':mom_3m,'mom_6m':mom_6m,'mom_12_1':mom_12_1,
        'vol_scalar':vol_scalar,'mom_vol_20d':mom_vol_20d,
        'mom_quality':mom_quality,
        'obv':obv,  # full OBV value — slope calculated per-base in UC-06
        'adl_ratio':adl_ratio,
        'vol_ratio_20':vol_ratio_20,'vol_ratio_50':vol_ratio_50,
        'week52_high':week52_high,'week52_low':week52_low,
        'pct_from_high':pct_from_high,
        'delivery_trend':delivery_trend  # display only
    }
```

---

### UC-03: Market Regime Detection (Engine C)

**Postcondition:** Regime score, crash warning, allocation params stored.

**6 signals + crash indicator:**

| Signal | Rule | Score |
|--------|------|-------|
| S1 Nifty vs 200MA | Nifty close > MA200 | 0 or 1 |
| S2 200MA slope | MA200 today > MA200 20d ago | 0 or 1 |
| S3 Breadth | % stocks above 50MA: >60%=1, 40-60%=0.5, <40%=0 | 0–1 |
| S4 Highs vs lows | New highs/lows ratio: >2x=1, equal=0.5, lows>highs=0 | 0–1 |
| S5 Extension | Nifty distance from 200MA: 0-15%=1, 15-25%=0.5, >25%=0 | 0–1 |
| S6 Index momentum | Nifty 12-1 month return positive | 0 or 1 |

**Momentum crash indicator (Dierkes & Krupski 2022):**
```python
nifty_2yr_return = (nifty_today / nifty_504d_ago) - 1
nifty_1m_return  = (nifty_today / nifty_21d_ago) - 1
crash_warning    = (nifty_2yr_return < -0.20) and (nifty_1m_return > 0.10)
# Both conditions together = momentum crash risk (2009, 2020 events)
# Force regime to Bear if crash_warning = True regardless of score
```

**Regime allocation table:**

| Score | Regime | Max Equity | Max Positions | Risk/Trade |
|-------|--------|-----------|--------------|-----------|
| 5.0–6.0 | Strong Bull | 100% | 15 | 2.0% |
| 4.0–5.0 | Bull | 80% | 12 | 1.5% |
| 2.5–4.0 | Weak | 50% | 8 | 1.0% |
| 1.0–2.5 | Bear | 25% | 4 (existing only) | 0.5% |
| 0–1.0 or crash | Full Bear | 0% | 0 | Exit all |

**Stability rule:** Regime changes only after 3 consecutive days at new level.

**Backtest Test 3 validation events:**
- 2018 mid-cap crash → regime Weak/Bear by Q3 2018?
- March 2020 → Bear within 5 trading days?
- April 2020 → crash indicator fires? (2yr down + 1m rally)
- 2022 rate hike → Bear correctly during FII selloff?

---

### UC-04: Momentum Ranking and Eligible Universe (Engine A)

**Postcondition:** Eligible Universe of 60–80 stocks with
volatility-scaled + fundamental bonus composite scores.

#### Hard Universe Filters (4 Only)

```python
def passes_hard_filters(stock, fundamentals, as_of_date):
    # 1. Market cap band
    if not (2000 <= stock['market_cap_cr'] <= 30000):
        return False, 'market_cap'

    # 2. Minimum liquidity
    if stock['avg_daily_tv_cr'] < 15:
        return False, 'illiquid'

    # 3. Not under surveillance
    if stock['is_asm'] or stock['is_esm']:
        return False, 'surveillance'

    # 4. Junk filter — not a persistent loss-maker
    # CRITICAL: reporting_date <= as_of_date
    recent_4q = get_fundamentals(db, stock['symbol'], as_of_date, limit=4)
    if sum(1 for q in recent_4q if q['eps'] > 0) < 2:
        return False, 'persistent_loss_maker'

    return True, None
```

#### Momentum Composite Score

```python
def build_composite_score(symbol, indicators, universe_indicators,
                           fundamentals, sector_rank, fii_data, as_of_date):

    # Step 1: Normalise momentum factors to 0-100 percentile within universe
    m12_1 = percentile_rank(indicators['mom_12_1'], universe_indicators['mom_12_1'])
    m6m   = percentile_rank(indicators['mom_6m'],   universe_indicators['mom_6m'])
    m3m   = percentile_rank(indicators['mom_3m'],   universe_indicators['mom_3m'])

    # Step 2: Weighted composite (update weights after Backtest Test 1)
    raw_score = (m12_1*0.40) + (m6m*0.35) + (m3m*0.25)

    # Step 3: Volatility scaling (Barroso & Santa-Clara 2015)
    actual_vol = indicators['mom_vol_20d'] * (252**0.5) * 100
    vol_scalar = min(20.0/actual_vol, 2.0) if actual_vol > 0 else 1.0
    scaled_score = raw_score * vol_scalar

    # Step 4: Fundamental bonus scores (NOT hard filters)
    f_bonus = calculate_fundamental_bonus(symbol, fundamentals, as_of_date)

    # Step 5: Accumulation bonus scores
    acc_bonus = 0
    if indicators['adl_ratio'] >= 0.60:    acc_bonus += 4  # A/D ratio
    # OBV bonus calculated in UC-06 during pattern detection (base-specific)
    # Smart institutional flow bonus (NEW — replaces simple FII sector flow)
    # Cannot blindly use FII for stocks where:
    # 1. Promoter holding > 65% (little room for FII)
    # 2. Defence/PSU sector (sectoral FII cap)
    # 3. Stock on NSE breach/caution list (FII buying legally blocked)
    inst_signal = calculate_smart_institutional_signal(
        symbol, fii_data, dii_data, bulk_deals,
        promoter_holding_pct, is_fii_capped_sector, is_on_breach_list
    )
    if inst_signal:
        acc_bonus += 2

    # Step 6: Sector bonus/penalty
    sector_bonus = 10 if sector_rank <= 3 else (-5 if sector_rank >= total_sectors-2 else 0)

    composite = scaled_score + f_bonus + acc_bonus + sector_bonus
    return composite, scaled_score, vol_scalar, f_bonus, acc_bonus
```

#### Fundamental Bonus Scores

```python
def calculate_fundamental_bonus(symbol, fundamentals, as_of_date):
    """
    Global evidence (Novy-Marx 2015, AQR, He & Narayanamoorthy 2017):
    Fundamentals as BONUS SCORES alongside momentum — not hard eliminators.
    Hard filters shrink universe without proportional return benefit.
    NSE Momentum 30: zero fundamentals → 19% CAGR vs 13% Nifty.
    """
    bonus = 0
    # CRITICAL: fundamentals filtered by reporting_date <= as_of_date
    funds = get_fundamentals(db, symbol, as_of_date, limit=4)
    if not funds: return 0
    latest = funds[0]

    # Bonus 1: Earnings acceleration (+8) — highest evidence globally
    # He & Narayanamoorthy 2017: acceleration predicts returns
    if len(funds) >= 3:
        g = [f.get('eps_growth_yoy', 0) or 0 for f in funds[:3]]
        if g[0] > g[1] > g[2] and g[0] > 0:
            bonus += 8

    # Bonus 2: EPS growth 15%+ (+5) — reward not eliminate
    eps_growth = latest.get('eps_growth_yoy', 0) or 0
    if eps_growth >= 15:   bonus += 5
    elif eps_growth >= 0:  bonus += 2

    # Bonus 3: Analyst upward revision (+4) — AQR uses this
    if (latest.get('analyst_revision') or 0) > 0:
        bonus += 4

    # Bonus 4: Low leverage (+3 max) — skip financial companies
    if not latest.get('is_financial', False):
        de = latest.get('debt_to_equity')
        if de is not None:
            if de < 1.0:   bonus += 3
            elif de < 1.5: bonus += 2
            elif de < 2.0: bonus += 1
            elif de > 3.0: bonus -= 2  # penalty, not elimination

    # REMOVED: delivery % bonus — zero evidence, operator contaminated
    # Replaced by: OBV bonus (in UC-06) and smart institutional flow (above)

    return min(max(bonus, -5), 20)


def calculate_smart_institutional_signal(symbol, fii_data, dii_data,
                                          bulk_deals, promoter_pct,
                                          is_fii_capped_sector,
                                          is_on_breach_list):
    """
    Smart institutional flow signal — India-specific.

    Problem: Cannot blindly use FII data for all stocks because:
    1. High promoter holding (>65%) leaves little room for FII buying
       SEBI requires max 75% promoter — many mid-caps close to this limit
    2. Sectoral FII caps — defence (49%), PSU banks (20%), print media (26%)
       HAL, BEL, BEML have strong momentum but FII cannot drive accumulation
    3. FII breach list — when aggregate FII hits the cap, NSE blocks further buying
       Stock on breach list means FII signal = 0 even if they want to buy

    Solution: Use the right signal for each stock based on its constraints.
    """
    # Case 1: High promoter holding — FII has no room, use DII
    if promoter_pct > 75 or is_fii_capped_sector or is_on_breach_list:
        # Use bulk deal data — known institution buying in bulk = strongest signal
        recent_bulk = bulk_deals[
            (bulk_deals['symbol'] == symbol) &
            (bulk_deals['date'] >= today - timedelta(days=10)) &
            (bulk_deals['deal_type'] == 'buy') &
            (bulk_deals['is_institution'] == True)
        ]
        return len(recent_bulk) > 0  # known institution bought in last 10 days

    # Case 2: Moderate promoter — FII limited, DII is primary
    elif promoter_pct > 65:
        # Use DII net flow for this stock's sector
        sector = get_stock_sector(symbol)
        dii_sector_flow = dii_data[dii_data['sector'] == sector]['dii_net_buy_cr'].tail(5).sum()
        return dii_sector_flow > 0  # DII net buyer in sector over 5 days

    # Case 3: Low promoter — FII + DII both meaningful
    else:
        # Use combined FII + DII sector flow
        sector = get_stock_sector(symbol)
        fii_flow = fii_data[fii_data['sector'] == sector]['fii_net_buy_cr'].tail(5).sum()
        dii_flow = dii_data[dii_data['sector'] == sector]['dii_net_buy_cr'].tail(5).sum()
        combined = fii_flow + dii_flow
        return combined > 0  # net institutional buyer in sector
```

---

### UC-05: Trend Template Screening (Engine B — Step 1)

**All 8 conditions hard gates — any failure = excluded:**

| # | Condition | Rule |
|---|-----------|------|
| 1 | Price > MA50 | `adj_close > ma50` |
| 2 | Price > MA150 | `adj_close > ma150` |
| 3 | Price > MA200 | `adj_close > ma200` |
| 4 | MA50 > MA150 | `ma50 > ma150` |
| 5 | MA150 > MA200 | `ma150 > ma200` |
| 6 | MA200 slope rising | `ma200_slope > 0` |
| 7 | Within 20% of 52W high | `adj_close >= week52_high * 0.80` |
| 8 | Stage 2 established | 20+ consecutive days above MA200 |

*Backtest Test 4 will tell us if 20% or 25% for Condition 7 is better on NSE.*

---

### UC-06: Pattern Detection (Engine B — Step 2)

#### Pattern 1 — VCP (Full Mathematical Definition)

```python
def detect_vcp(symbol, prices, volumes, as_of_date):
    # Step 1: Find base start (most recent pivot high)
    recent_252 = prices.tail(252)
    pivot_high  = recent_252['adj_close'].max()
    base_start  = recent_252['adj_close'].idxmax()
    base_prices = prices.loc[base_start:]

    # Step 2: Extract and validate contractions
    contractions = find_contractions(base_prices)
    if len(contractions) < 3: return None

    depths = [c['depth_pct'] for c in contractions]
    if not all(depths[i] < depths[i-1] for i in range(1,len(depths))):
        return None  # not getting shallower

    avg_vols = [c['avg_volume'] for c in contractions]
    if avg_vols[-1] >= avg_vols[0]:
        return None  # volume not declining

    # Step 3: Base validation
    base_weeks = len(base_prices) / 5
    depth_overall = (pivot_high - base_prices['adj_close'].min()) / pivot_high
    if base_weeks < 5 or base_weeks > 52: return None
    if depth_overall > 0.40: return None

    # Step 4: NSE circuit exclusion
    if had_circuit_lock(symbol, base_prices.index):
        return None  # circuit-locked patterns are NOT genuine VCPs

    # Step 5: OBV slope during base (NEW — replaces delivery signal)
    # IMPORTANT: calculate OBV slope from base_start ONLY
    # Do NOT use full-history OBV — news spikes before base distort it
    base_vols   = volumes.loc[base_start:]
    base_closes = base_prices['adj_close']
    sign        = base_closes.diff().apply(lambda x: 1 if x>0 else (-1 if x<0 else 0))
    obv_base    = (sign * base_vols).cumsum()
    obv_slope   = np.polyfit(range(len(obv_base)), obv_base, 1)[0]
    # Positive slope = volume pressure building during base = accumulation
    obv_bonus   = 5 if obv_slope > 0 else 0

    # OBV divergence: price makes lower low but OBV makes higher low
    price_ll = base_prices['adj_close'].tail(20).min() < base_prices['adj_close'].iloc[20:40].min()
    obv_hl   = obv_base.tail(20).min() > obv_base.iloc[20:40].min()
    obv_divergence = price_ll and obv_hl  # extra bullish signal

    # Step 6: Pivot and entry zone
    pivot = contractions[-1]['high']
    return {
        'pattern_type':      'VCP',
        'pivot_price':       pivot,
        'stop_loss':         base_prices['adj_close'].min(),
        'entry_zone_low':    pivot,
        'entry_zone_high':   pivot * 1.05,
        'base_length_days':  len(base_prices),
        'base_depth_pct':    depth_overall,
        'obv_slope':         obv_slope,
        'obv_bonus':         obv_bonus,
        'obv_divergence':    obv_divergence,  # display in dashboard
        'contraction_count': len(contractions),
    }
```

#### Entry Rules (Engine B — Step 3)

```python
def check_entry_valid(signal, today, next_day_open=None):
    """
    All conditions must pass for a valid entry.
    """
    # Condition 1: Price closed above pivot (breakout day)
    if today['adj_close'] <= signal['pivot_price']:
        return False, 'no_breakout'

    # Condition 2: Volume expansion (primary accumulation signal)
    if today['vol_ratio_50'] < 1.5:
        return False, 'insufficient_volume'

    # Condition 3: Strong close (not a reversal bar)
    day_range = today['high'] - today['low']
    if day_range > 0:
        close_position = (today['adj_close'] - today['low']) / day_range
        if close_position < 0.75:
            return False, 'weak_close'

    # Condition 4: Not too extended above pivot
    if today['adj_close'] > signal['pivot_price'] * 1.05:
        return False, 'too_extended'

    # Condition 5: Circuit breaker check
    if today.get('hit_upper_circuit', False):
        return False, 'upper_circuit'

    # Condition 6: Earnings safety rule (NEW — critical for India)
    # If results due within 10 trading days → do not enter
    days_to_results = get_days_to_next_results(signal['symbol'])
    if days_to_results is not None and days_to_results <= 10:
        return False, 'earnings_too_close'

    # Condition 7: Max entry price rule (NEW — prevents chasing gaps)
    # If next-day open is more than 3% above pivot → signal expires
    if next_day_open is not None:
        if next_day_open > signal['pivot_price'] * 1.03:
            return False, 'gap_too_large'

    return True, None
```

#### False Breakout Filter

```python
def update_pending_signals(db, as_of_date):
    """
    40-60% of NSE breakouts fail within 2 days.
    Day 1: breakout detected → Pending
    Day 2: price holds above pivot → Confirmed
            price falls below pivot → Failed
    Only Confirmed signals enter watchlist as Tier 1.
    """
    for signal in get_pending_signals(db):
        today_price = get_adj_close(db, signal['symbol'], as_of_date)
        if today_price > signal['pivot_price']:
            update_status(signal['id'], 'Confirmed', as_of_date)
        else:
            update_status(signal['id'], 'Failed', as_of_date)
```

---

### UC-07: Position Sizing (Engine C)

```python
def calculate_position_size(portfolio_value, regime_params,
                             signal, portfolio_vol_scalar):
    # Apply portfolio-level volatility scaling
    adj_risk = regime_params['risk_pct'] * portfolio_vol_scalar

    entry_mid   = (signal['entry_zone_low'] + signal['entry_zone_high']) / 2
    risk_per_sh = entry_mid - signal['stop_loss']

    if risk_per_sh <= 0: return None

    risk_amt = portfolio_value * (adj_risk / 100)
    shares   = int(risk_amt / risk_per_sh)
    pos_val  = shares * entry_mid
    pos_pct  = min(pos_val / portfolio_value, 0.20)  # cap 20%
    pos_pct  = max(pos_pct, 0.02)                    # floor 2%

    return {
        'shares': int(pos_pct * portfolio_value / entry_mid),
        'position_value': pos_pct * portfolio_value,
        'position_pct': pos_pct,
        'risk_amount': risk_amt,
    }

def check_portfolio_constraints(new_signal, open_positions, portfolio_value):
    # Heat check
    current_heat = sum(
        p['value'] * (p['entry']-p['stop'])/p['entry']
        for p in open_positions
    ) / portfolio_value
    new_heat = new_signal['risk_amount'] / portfolio_value
    if current_heat + new_heat > 0.06:
        return False, 'heat_exceeded'

    # Sector cap
    sector_total = sum(
        p['value'] for p in open_positions
        if p['sector'] == new_signal['sector']
    )
    if (sector_total + new_signal['position_value']) / portfolio_value > 0.30:
        return False, 'sector_cap'

    return True, None
```

---

### UC-08: Watchlist Generation

**Output fields per stock:**

| Field | Description |
|-------|-------------|
| rank | 1–20 |
| symbol | NSE ticker |
| tier | 1=Buy Now / 2=Near Pivot / 3=On Radar |
| composite_score | Full score |
| momentum_score | Pure momentum component |
| fundamental_bonus | Bonus points (accelerating EPS etc.) |
| obv_bonus | OBV accumulation bonus (0 or 5) |
| obv_divergence | True/False — bullish divergence detected |
| adl_ratio | 20-day accumulation/distribution |
| delivery_trend | Rising/Flat/Falling — display context only |
| fii_sector_flow | FII net buyer in sector (True/False) |
| pattern_type | VCP / TightBase / Breakout |
| status | Confirmed / Pending / Forming |
| entry_zone | Low–High |
| stop_loss | Base low |
| suggested_size_pct | % of portfolio |
| vol_scalar | Volatility scaling factor |
| earnings_date | Next results date — safety context |
| days_to_earnings | Trading days until next results |
| earnings_flag | True if results due within 10 days |
| regime | Current regime |

**Tier logic:**
- Tier 1: Confirmed breakout + regime Bull+ + score above threshold
- Tier 2: Within 3% of pivot + score above 65 + base confirmed
- Tier 3: Eligible Universe + score above 55 + base forming
  **OR** any Tier 1/2 signal with earnings due within 10 days

---

### UC-09: Exit Engine

**All exit rules checked daily for every open position:**

| Exit | Trigger | Action |
|------|---------|--------|
| Initial stop | today low < current_stop | Full exit |
| Breakeven | gain >= 20% AND stop < entry | Move stop to entry |
| Trail 40% | gain >= 40% | Trail 10% below 10-day high |
| Trail 100% | gain >= 100% | Trail 15% below 10-day high |
| Time stop | holding >= 20 days AND abs(gain) < 5% | Full exit |
| Climax | gain >= 20% in < 15 days | Sell 50% |
| Regime | Bear or crash warning | Exit 20%/day for 5 days |
| MA200 breach | adj_close < ma200 | Mandatory full exit |
| Rebalance | RS rank below top 40% for 2 weeks | Exit signal |

**Exit reasons stored:** stop/trailing/time/climax/regime/technical/rebalance/manual

---

### UC-10: Backtesting — 10 Tests Before Any Live Trading

**Execution rules (non-negotiable for all tests):**
```
Entry price:     Next day open — never same-day close
Slippage:        +0.5% entry, -0.5% exit
Brokerage:       0.1% per side
STT:             0.1% on sell
Exchange:        0.05% per side
Round trip:      ~0.4% total
Position sizing: Fixed fractional 2% risk per trade
Circuit:         Skip entry if stock hit upper circuit on signal day
Fundamentals:    reporting_date <= backtest_date strictly enforced
Universe:        Includes all delisted stocks — no survivorship bias
```

#### Test 1 — Momentum Factor Weights
```
1A: 3m alone | 1B: 6m alone | 1C: 12-1 alone
1D: Equal 33/33/33 | 1E: Default 40/35/25
1F: Default + volatility scaling (expected winner)
Gate: Best beats Nifty 50 Sharpe by 0.3+
```

#### Test 2 — Market Cap Band
```
2A: All NSE (baseline) | 2B: 500–30,000cr
2C: 1,000–30,000cr | 2D: 2,000–30,000cr (current)
2E: 2,000–20,000cr | 2F: 3,000–25,000cr
Gate: Chosen band beats baseline Sharpe AND drawdown
```

#### Test 3 — Regime Filter
```
3A: No filter | 3B: 200MA only
3C: 5-signal regime | 3D: 5-signal + crash indicator
Critical: crash indicator must fire April 2020
Gate: Filter reduces max drawdown 30%+
```

#### Test 4 — Trend Template
```
4A: No template | 4B: 6 conditions
4C: 8 conditions 20% | 4D: 8 conditions 25%
Gate: Improves win rate 5%+ OR Sharpe 0.2+
If fails: remove template entirely
```

#### Test 5 — Fundamental Approach
```
5A: No filter (NSE Momentum 30 style)
5B: EPS 15% hard filter (old approach)
5C: Junk filter only (current approach)
5D: Junk filter + bonus scores (v7 approach)
5E: Heavy CANSLIM (EPS+ROE+Revenue)
Gate: 5D must beat 5B on out-of-sample Sharpe
If 5A beats 5D: remove even junk filter
```

#### Test 6 — VCP Win Rate
```
Scan 2015-2024 for all VCP signals
6A: All VCP breakouts — win rate, avg win/loss
6B: Random entry from eligible universe (control)
6C: Tight base breakouts
6D: With vs without OBV bonus in detection
Gate: VCP win rate > 45%, avg win >= 2x avg loss
If fails: remove pattern detection, use momentum entry only
```

#### Test 7 — Exit Rules
```
7A: Fixed 8% stop | 7B: 10-day MA trail
7C: 20-day MA trail | 7D: Tiered exit (v7 spec)
7E: 7D + time stop | 7F: 7E + climax exit
Gate: Best Calmar ratio (CAGR/max drawdown)
```

#### Test 8 — Rebalancing Frequency (net of full costs)
```
8A: Weekly | 8B: Monthly | 8C: Semi-annual
8D: Signal-based (RS rank drop below 40%)
Gate: Best net-of-cost Calmar ratio
Note: Weekly likely too frequent for NSE mid-caps
```

#### Test 9 — Volume + Institutional Signals Validation

```
Part A — OBV vs delivery (original test):
9A: Full system — no volume bonus beyond breakout ratio
9B: Full system + OBV slope bonus (+5)
9C: Full system + A/D ratio bonus (+4)
9D: Full system + OBV + A/D (all volume bonuses)
9E: Full system + old delivery % bonus — for comparison

Gate: 9D beats 9A on OOS Sharpe
Gate: 9D beats 9E (OBV better than delivery %)

Part B — Smart institutional flow validation (NEW):
9F: Full system — no institutional flow bonus at all
9G: Full system + blind FII sector flow (naive approach, ignores promoter/caps)
9H: Full system + smart institutional flow (FII/DII/bulk deal per stock)

Specifically test on stocks where:
- Promoter holding > 65% (HAL, BEL, many PSU stocks)
- Stocks on NSE breach list in the historical period
- Defence sector stocks

Gate: 9H must beat 9G on OOS Sharpe (smart signal better than blind FII)
Gate: 9H must show higher win rate on high-promoter stocks vs 9G
Action: If 9F beats 9H: remove institutional signal entirely,
        keep only OBV and A/D as accumulation signals
```

#### Test 10 — Full Integrated System
```
Period: 2015–2024 (10 years)
Parameters: Use winning settings from Tests 1–9
Universe: Including all delisted stocks

Required 14 metrics:
1.  CAGR annualised
2.  Nifty 50 alpha
3.  Win rate %
4.  Average win %
5.  Average loss %
6.  Win/loss ratio
7.  Expectancy (Rs. and %)
8.  Maximum drawdown %
9.  Sharpe ratio
10. Calmar ratio
11. Performance by regime (each separately)
12. Average holding period
13. Annual returns 2015–2024
14. Best and worst year

Hard gates (ALL must pass):
[ ] Positive expectancy
[ ] Sharpe > 0.8
[ ] Max drawdown < 25%
[ ] CAGR > 15%
[ ] Outperforms Nifty 50 by 5%+ CAGR
[ ] Positive in at least 3 of 4 regime types
```

---

### UC-11: Walk-Forward Validation

**Two types — both required:**

#### Expanding Window (Primary)
```
Fold 1: Train 2015–2018 | Test 2019–2020 (COVID crash)
Fold 2: Train 2015–2019 | Test 2020–2021 (V-recovery)
Fold 3: Train 2015–2020 | Test 2021–2022 (inflation bear)
Fold 4: Train 2015–2021 | Test 2022–2024 (recent bull)

Gate: OOS Sharpe >= 70% of IS Sharpe in ALL 4 folds
```

#### Rolling Window (NEW — Secondary, stricter test)
```
Fold 5: Train 2015–2018 | Test 2019–2020
Fold 6: Train 2017–2020 | Test 2021–2022
Fold 7: Train 2019–2022 | Test 2023–2024

Gate: Rolling-window OOS Sharpe not materially worse than
      expanding-window (within 15 percentage points)
If rolling-window significantly worse: system relies on
early historical period — warning sign for future performance
```

---

### UC-12: Paper Trading (3 Months Mandatory)

```
Duration: 60+ trading days minimum

Daily tracking:
- Every signal with timestamp, pattern type, tier
- Would-have-been P&L at actual next-day open
- Earnings flag accuracy (did system flag results correctly?)
- Max entry price rule triggers (how often do gaps exceed 3%?)
- Regime calls vs your own market view

Weekly chart review:
- Look at chart of every Tier 1 signal
- Does VCP base look genuine visually?
- Is OBV rising during the base as expected?
- Are earnings dates showing correctly?

Go-live gate:
[ ] 95%+ pipeline success rate (60 days)
[ ] Live win rate within 10% of backtest
[ ] 15+ Tier 1 signals generated and reviewed
[ ] Regime calls match owner's view 80%+ of days
[ ] Earnings flag correctly identified at least 5 pre-earnings situations
[ ] Max entry rule triggered at least 3 times (proves it works)
[ ] Owner confident in signal quality
```

---

### UC-13: Go-Live Decision Checklist

**Nothing gets real money until all 12 gates pass:**

**Component backtest gates:**
- [ ] Test 1: Optimal weights → settings.py updated
- [ ] Test 2: Optimal market cap band → settings.py updated
- [ ] Test 3: Regime filter cuts drawdown 30%+ | crash fires April 2020
- [ ] Test 4: Trend template adds value (or removed with evidence)
- [ ] Test 5: Bonus scores beat hard filters on OOS Sharpe
- [ ] Test 6: VCP win rate > 45%, avg win >= 2x avg loss
- [ ] Test 7: Best exit rule → settings.py updated
- [ ] Test 8: Best rebalancing frequency → settings.py updated
- [ ] Test 9: OBV bonus beats delivery bonus on OOS Sharpe
- [ ] Test 10: Full system — all 6 hard gates passed

**System validation gates:**
- [ ] adj_close verified on 10 known corporate action events
- [ ] reporting_date verified — zero look-ahead bias on 20 checks
- [ ] Crash indicator verified — fires April 2020 condition

**Walk-forward gates:**
- [ ] Expanding-window: OOS Sharpe >= 70% IS in all 4 folds
- [ ] Rolling-window: not materially worse than expanding

**Paper trading gates:**
- [ ] 60+ trading days complete
- [ ] All paper trading items checked above
- [ ] Earnings date safety rule verified in real scenarios

**Live deployment:**
- Month 1: 25% of intended capital
- Month 2: 50% if live performance within 20% of backtest
- Month 3+: Full capital after consistent validation

---

### UC-14: Daily Live Pipeline

| Step | Action | Time |
|------|--------|------|
| 1 | Holiday check | 10s |
| 2 | Download bhav copy + delivery data | 3 min |
| 3 | Download FII/DII data | 1 min |
| 4 | Check corporate actions | 2 min |
| 5 | Data validation gate | 2 min |
| 6 | Update price_data (raw + adj_close) | 2 min |
| 7 | Calculate all indicators + OBV | 5 min |
| 8 | Calculate regime + crash indicator | 2 min |
| 9 | Rank universe (momentum + vol scaling) | 3 min |
| 10 | Calculate fundamental bonus scores | 2 min |
| 11 | Calculate FII sector flow bonus | 1 min |
| 12 | Apply trend template (8 conditions) | 2 min |
| 13 | Detect VCP/base/breakout + OBV slope | 4 min |
| 14 | Confirm/fail yesterday's Pending signals | 1 min |
| 15 | Check earnings dates (flag if <10 days) | 1 min |
| 16 | Calculate positions + heat + sector check | 2 min |
| 17 | Generate watchlist (max 20) | 1 min |
| 18 | Check exit signals (all open positions) | 2 min |
| 19 | Update performance tracker | 1 min |
| 20 | Refresh dashboard | 1 min |
| 21 | Send WhatsApp + email alerts | 2 min |
| **Total** | | **~40 min** |

**Dashboard live by 5:00 PM IST.**

---

### UC-15: Performance Tracking

**Every trade logged:**

| Field | Description |
|-------|-------------|
| entry_price | Planned vs actual fill (slippage measurement) |
| exit_reason | stop/trailing/time/climax/regime/technical/rebalance/manual |
| pnl_pct | P&L percentage |
| max_gain_pct | MFE — max favourable excursion |
| max_loss_pct | MAE — max adverse excursion |
| pattern_type | VCP / TightBase / Breakout |
| regime_at_entry | Which regime at entry |
| vol_scalar | Volatility scalar applied |
| obv_bonus | OBV score at entry |
| earnings_flagged | Was earnings flag shown at entry? |
| days_to_earnings | Days to results at entry date |

**Monthly review:**
1. Live win rate vs backtest win rate — within 10%?
2. Live slippage vs 0.5% assumption — matching?
3. Which pattern type has best live win rate?
4. Earnings flag helping (are flagged stocks underperforming unflagged)?
5. Max entry 3% rule — how many times triggered? Good or too restrictive?
6. OBV bonus stocks — are they outperforming non-OBV stocks?

---

### UC-16: Subscription Tiers

**Pricing rationale:** These are institutional-grade signals from a backtested
10-year NSE system. Comparable tools globally (MarketSmith US: ₹8,000/mo,
Minervini's own service: $1,000+/mo). Positioned as a premium Indian product
for serious traders and HNI investors.

| Tier | Monthly | Annual (2 months free) | Target User |
|------|---------|----------------------|-------------|
| Starter | ₹2,999 | ₹29,990 | Active retail trader, 1–5 stocks/month |
| Pro | ₹9,999 | ₹99,990 | Serious trader, 5–15 stocks/month |
| Institutional | ₹30,000+ | ₹3,00,000+ | HNI, family office, PMS, fund manager |

**Institutional tier is custom-priced** — starts at ₹30,000/month and goes
higher based on AUM size, number of accounts, and customisation required.
This tier requires a sales call before activation.

| Feature | Starter ₹2,999/mo | Pro ₹9,999/mo | Institutional ₹30,000+/mo |
|---------|-------------------|--------------|--------------------------|
| **Market intelligence** | | | |
| Regime indicator + crash warning | ✅ | ✅ | ✅ |
| Top 10 watchlist stock names | ✅ | ✅ | ✅ |
| Sector rotation rankings | ❌ | ✅ | ✅ |
| FII sector flow indicator | ❌ | ✅ | ✅ |
| **Daily signals** | | | |
| Full Tier 1 signals (entry, stop, size) | ❌ | ✅ | ✅ |
| Full Tier 2 near-pivot signals | ❌ | ✅ | ✅ |
| OBV divergence per signal | ❌ | ✅ | ✅ |
| Earnings date safety flag | ❌ | ✅ | ✅ |
| Delivery % context (display) | ❌ | ✅ | ✅ |
| Volatility scalar per signal | ❌ | ✅ | ✅ |
| **Alerts** | | | |
| WhatsApp alerts | ❌ | ✅ | ✅ |
| Email alerts | ❌ | ✅ | ✅ |
| Regime change alerts | ❌ | ✅ | ✅ |
| **Research** | | | |
| Historical signal archive | ❌ | ✅ | ✅ |
| Backtest results access | ❌ | ✅ | ✅ |
| Performance stats by pattern | ❌ | ✅ | ✅ |
| **Execution (Institutional only)** | | | |
| Zerodha auto-execution | ❌ | ❌ | ✅ |
| Multi-account execution | ❌ | ❌ | ✅ |
| Custom position size limits | ❌ | ❌ | ✅ |
| Portfolio P&L tracking | ❌ | ❌ | ✅ |
| Custom risk parameters | ❌ | ❌ | ✅ |
| **Support** | | | |
| Email support | ✅ | ✅ | ✅ |
| Priority WhatsApp support | ❌ | ✅ | ✅ |
| Dedicated onboarding call | ❌ | ❌ | ✅ |
| Monthly strategy review call | ❌ | ❌ | ✅ |
| **API & integration** | | | |
| Full REST API access | ❌ | ❌ | ✅ |
| Webhook signal delivery | ❌ | ❌ | ✅ |
| Custom data export | ❌ | ❌ | ✅ |

**Business rules:**
- All tiers: 7-day free trial (no credit card required for Starter and Pro)
- Institutional tier: requires sales call, minimum 3-month commitment
- Annual billing: 2 months free (pay 10, get 12)
- No refunds after signals delivered for the month
- SEBI compliance note: platform is a research and screening tool —
  not a SEBI-registered investment advisor
- Institutional subscribers execute via their own Zerodha accounts —
  platform does not hold or manage client funds

---

## 5. Database Schema

```sql
CREATE TABLE stocks (
    symbol            VARCHAR(20) PRIMARY KEY,
    name              VARCHAR(100),
    isin              VARCHAR(20) UNIQUE,
    sector            VARCHAR(50),
    industry          VARCHAR(50),
    listing_date      DATE,
    market_cap_cr     DECIMAL(14,2),
    free_float_pct    DECIMAL(5,2),
    avg_daily_tv_cr   DECIMAL(10,2),
    is_asm            BOOLEAN DEFAULT FALSE,
    is_esm            BOOLEAN DEFAULT FALSE,
    is_financial      BOOLEAN DEFAULT FALSE,
    is_fii_capped_sector BOOLEAN DEFAULT FALSE,  -- defence/PSU/low-FDI sectors
    promoter_holding_pct DECIMAL(5,2),           -- from quarterly shareholding
    fii_holding_pct    DECIMAL(5,2),             -- current FII holding %
    dii_holding_pct    DECIMAL(5,2),             -- current DII holding %
    fii_headroom_pct   DECIMAL(5,2),             -- room left for FII buying
    is_fii_breached    BOOLEAN DEFAULT FALSE,    -- on NSE breach list
    is_fii_cautioned   BOOLEAN DEFAULT FALSE,    -- on NSE caution list
    shareholding_date  DATE,                     -- last update of holding data
    status            VARCHAR(20) DEFAULT 'active',
    delisted_date     DATE
);

CREATE TABLE price_data (
    symbol              VARCHAR(20),
    date                DATE,
    open                DECIMAL(12,2),
    high                DECIMAL(12,2),
    low                 DECIMAL(12,2),
    close               DECIMAL(12,2),
    adj_close           DECIMAL(12,2) NOT NULL,
    adj_factor          DECIMAL(10,6) DEFAULT 1.0,
    volume              BIGINT,
    traded_value_cr     DECIMAL(14,2),
    delivery_qty        BIGINT,
    delivery_pct        DECIMAL(5,2),  -- stored, displayed, NOT scored
    hit_upper_circuit   BOOLEAN DEFAULT FALSE,
    hit_lower_circuit   BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE fundamentals (
    id                    SERIAL PRIMARY KEY,
    symbol                VARCHAR(20),
    period_end_date       DATE,
    reporting_date        DATE NOT NULL,  -- ALWAYS filter by this
    quarter               VARCHAR(10),
    eps                   DECIMAL(10,2),
    eps_growth_yoy        DECIMAL(8,2),
    revenue_cr            DECIMAL(14,2),
    roe                   DECIMAL(8,2),
    debt_to_equity        DECIMAL(8,2),
    analyst_revision      DECIMAL(8,2),
    expected_result_date  DATE,          -- upcoming results date (NEW)
    is_financial          BOOLEAN DEFAULT FALSE,
    UNIQUE (symbol, period_end_date)
);

CREATE TABLE indicators (
    symbol          VARCHAR(20),
    date            DATE,
    ma50            DECIMAL(12,2),
    ma150           DECIMAL(12,2),
    ma200           DECIMAL(12,2),
    ma200_slope     DECIMAL(10,4),
    atr14           DECIMAL(12,2),
    rs_score_6m     DECIMAL(8,4),
    rs_rank         INTEGER,
    mom_3m          DECIMAL(8,4),
    mom_6m          DECIMAL(8,4),
    mom_12_1        DECIMAL(8,4),
    raw_score       DECIMAL(8,4),
    scaled_score    DECIMAL(8,4),
    vol_scalar      DECIMAL(6,4),
    mom_vol_20d     DECIMAL(8,4),
    mom_quality     DECIMAL(5,4),
    obv             DECIMAL(20,0),      -- full OBV value (slope per-base in signals)
    adl_ratio       DECIMAL(6,4),
    vol_ratio_20    DECIMAL(6,4),
    vol_ratio_50    DECIMAL(6,4),
    week52_high     DECIMAL(12,2),
    week52_low      DECIMAL(12,2),
    pct_from_high   DECIMAL(6,4),
    delivery_trend  DECIMAL(8,4),       -- display only, never scored
    PRIMARY KEY (symbol, date)
);

CREATE TABLE fii_dii_data (
    date              DATE PRIMARY KEY,
    fii_net_buy_cr    DECIMAL(14,2),
    dii_net_buy_cr    DECIMAL(14,2),
    sector_flows      JSONB              -- {sector: fii_net_buy} per sector
);

CREATE TABLE shareholding_pattern (
    symbol            VARCHAR(20),
    quarter_end_date  DATE,
    promoter_pct      DECIMAL(5,2),
    fii_pct           DECIMAL(5,2),
    dii_pct           DECIMAL(5,2),
    public_pct        DECIMAL(5,2),
    fii_headroom_pct  DECIMAL(5,2),  -- 24% - current fii_pct (approx)
    PRIMARY KEY (symbol, quarter_end_date)
);

CREATE TABLE fii_breach_list (
    date              DATE,
    symbol            VARCHAR(20),
    breach_type       VARCHAR(20),   -- 'breached' or 'cautioned'
    fii_limit_pct     DECIMAL(5,2),
    current_fii_pct   DECIMAL(5,2),
    PRIMARY KEY (date, symbol)
);

CREATE TABLE bulk_deals (
    id                SERIAL PRIMARY KEY,
    date              DATE,
    symbol            VARCHAR(20),
    client_name       VARCHAR(200),
    deal_type         VARCHAR(10),   -- buy / sell
    quantity          BIGINT,
    price             DECIMAL(12,2),
    value_cr          DECIMAL(12,2),
    is_institution    BOOLEAN DEFAULT FALSE  -- known MF/insurance/FII name
);

CREATE TABLE signals (
    id                SERIAL PRIMARY KEY,
    signal_date       DATE,
    symbol            VARCHAR(20),
    pattern_type      VARCHAR(20),
    status            VARCHAR(20),       -- Pending/Confirmed/Failed/Expired
    pivot_price       DECIMAL(12,2),
    stop_loss         DECIMAL(12,2),
    entry_zone_low    DECIMAL(12,2),
    entry_zone_high   DECIMAL(12,2),
    volume_ratio      DECIMAL(6,4),
    obv_slope         DECIMAL(12,4),     -- OBV slope during base (NEW)
    obv_bonus         INTEGER,           -- 0 or 5
    obv_divergence    BOOLEAN,           -- bullish divergence detected
    adl_ratio         DECIMAL(6,4),
    delivery_trend    DECIMAL(8,4),      -- display context only
    inst_flow_signal  VARCHAR(20),        -- FII/DII/BulkDeal — source used
    inst_flow_positive BOOLEAN,           -- smart institutional signal positive
    base_length_days  INTEGER,
    base_depth_pct    DECIMAL(5,2),
    regime            VARCHAR(20),
    crash_warning     BOOLEAN,
    earnings_date     DATE,              -- next results date (NEW)
    days_to_earnings  INTEGER,           -- trading days to results (NEW)
    earnings_flag     BOOLEAN,           -- True if < 10 days (NEW)
    tier              INTEGER,
    composite_score   DECIMAL(8,4),
    vol_scalar        DECIMAL(6,4),
    fundamental_bonus INTEGER,
    confirmed_date    DATE,
    failed_date       DATE
);

CREATE TABLE watchlist (
    date               DATE,
    symbol             VARCHAR(20),
    rank               INTEGER,
    tier               INTEGER,
    composite_score    DECIMAL(8,4),
    momentum_score     DECIMAL(8,4),
    fundamental_bonus  INTEGER,
    obv_bonus          INTEGER,
    adl_ratio          DECIMAL(6,4),
    delivery_trend     DECIMAL(8,4),     -- display only
    inst_flow_signal   VARCHAR(20),
    inst_flow_positive BOOLEAN,
    pattern_type       VARCHAR(20),
    signal_id          INTEGER,
    entry_zone_low     DECIMAL(12,2),
    entry_zone_high    DECIMAL(12,2),
    stop_loss          DECIMAL(12,2),
    suggested_size_pct DECIMAL(5,2),
    vol_scalar         DECIMAL(6,4),
    earnings_date      DATE,
    earnings_flag      BOOLEAN,
    regime             VARCHAR(20),
    PRIMARY KEY (date, symbol)
);

CREATE TABLE performance_log (
    id                    SERIAL PRIMARY KEY,
    user_id               INTEGER,
    symbol                VARCHAR(20),
    entry_date            DATE,
    exit_date             DATE,
    entry_price           DECIMAL(12,2),
    actual_fill           DECIMAL(12,2),
    exit_price            DECIMAL(12,2),
    pnl_pct               DECIMAL(8,4),
    pnl_inr               DECIMAL(12,2),
    exit_reason           VARCHAR(30),
    holding_days          INTEGER,
    max_gain_pct          DECIMAL(8,4),
    max_loss_pct          DECIMAL(8,4),
    pattern_type          VARCHAR(20),
    regime_at_entry       VARCHAR(20),
    vol_scalar_at_entry   DECIMAL(6,4),
    obv_bonus_at_entry    INTEGER,
    earnings_flagged      BOOLEAN,
    days_to_earnings      INTEGER
);

CREATE TABLE backtest_results (
    id              SERIAL PRIMARY KEY,
    test_name       VARCHAR(50),
    run_date        TIMESTAMP DEFAULT NOW(),
    period_start    DATE,
    period_end      DATE,
    parameters      JSONB,
    cagr            DECIMAL(8,4),
    nifty_alpha     DECIMAL(8,4),
    win_rate        DECIMAL(5,4),
    avg_win         DECIMAL(8,4),
    avg_loss        DECIMAL(8,4),
    expectancy_pct  DECIMAL(8,4),
    max_drawdown    DECIMAL(8,4),
    sharpe_ratio    DECIMAL(8,4),
    calmar_ratio    DECIMAL(8,4),
    total_trades    INTEGER,
    avg_holding_days DECIMAL(6,1),
    bull_cagr       DECIMAL(8,4),
    weak_cagr       DECIMAL(8,4),
    bear_cagr       DECIMAL(8,4),
    annual_returns  JSONB,
    passed_gate     BOOLEAN,
    notes           TEXT
);

CREATE TABLE walkforward_results (
    id              SERIAL PRIMARY KEY,
    window_type     VARCHAR(20),     -- 'expanding' or 'rolling'
    fold            INTEGER,
    train_start     DATE,
    train_end       DATE,
    test_start      DATE,
    test_end        DATE,
    is_sharpe       DECIMAL(8,4),
    oos_sharpe      DECIMAL(8,4),
    oos_is_ratio    DECIMAL(8,4),
    is_cagr         DECIMAL(8,4),
    oos_cagr        DECIMAL(8,4),
    passed_gate     BOOLEAN
);

-- Indexes
CREATE INDEX idx_price_sym_date   ON price_data (symbol, date DESC);
CREATE INDEX idx_price_date       ON price_data (date DESC);
CREATE INDEX idx_ind_date_score   ON indicators (date DESC, scaled_score DESC);
CREATE INDEX idx_fund_sym_rdate   ON fundamentals (symbol, reporting_date DESC);
CREATE INDEX idx_fund_result_date ON fundamentals (symbol, expected_result_date);
CREATE INDEX idx_sig_date_tier    ON signals (signal_date DESC, tier, status);
CREATE INDEX idx_watch_date       ON watchlist (date DESC, rank);
CREATE INDEX idx_perf_user        ON performance_log (user_id, exit_date DESC);
```

---

## 6. Settings File

```python
# config/settings.py — update after backtesting

# Universe
MARKET_CAP_MIN_CR         = 2000
MARKET_CAP_MAX_CR         = 30000
MIN_DAILY_TRADED_VALUE_CR = 15
MIN_FREE_FLOAT_PCT        = 25
MIN_HISTORY_DAYS          = 200
BACKTEST_START            = '2015-01-01'
BACKTEST_END              = '2024-12-31'

# Momentum weights (update after Test 1)
MOM_WEIGHT_12_1 = 0.40
MOM_WEIGHT_6M   = 0.35
MOM_WEIGHT_3M   = 0.25

# Volatility scaling
VOL_TARGET_PCT       = 20.0
VOL_SCALAR_MAX       = 2.0
PORTFOLIO_VOL_TARGET = 0.15

# Filters and thresholds
RS_RANK_MIN_PCT       = 30
MOM_QUALITY_MIN       = 0.55
JUNK_MIN_POS_EPS_QTRS = 2

# Fundamental bonus scores
BONUS_EPS_ACCEL     = 8
BONUS_EPS_15        = 5
BONUS_EPS_POS       = 2
BONUS_ANALYST_REV   = 4
BONUS_LOW_DE_10     = 3
BONUS_LOW_DE_15     = 2
BONUS_LOW_DE_20     = 1
PENALTY_HIGH_DE_30  = -2

# Accumulation bonus scores
BONUS_OBV_RISING    = 5   # OBV slope positive during base
BONUS_ADL_RATIO     = 4   # A/D ratio >= 0.60
BONUS_INST_FLOW     = 2   # Smart institutional signal (FII/DII/bulk deal per stock)

# REMOVED: BONUS_DELIVERY = 0  (no evidence, operator contaminated)

# Sector bonus
SECTOR_TOP3_BONUS   = 10
SECTOR_BOTTOM3_PEN  = -5

# Regime
REGIME_STRONG_BULL  = 5.0
REGIME_BULL         = 4.0
REGIME_WEAK         = 2.5
REGIME_BEAR         = 1.0
REGIME_STABILITY    = 3    # days
CRASH_2YR_DOWN      = -0.20
CRASH_1M_RALLY      = 0.10

# Trend template
PCT_FROM_52W_HIGH   = 0.20  # test 0.25 in Test 4
MA200_SLOPE_DAYS    = 20
MIN_DAYS_ABOVE_200  = 20

# VCP
VCP_MIN_CONTRACTIONS  = 3
VCP_MAX_DEPTH         = 0.40
VCP_MIN_WEEKS         = 5
VCP_MAX_WEEKS         = 52
VCP_BREAKOUT_VOL      = 1.5

# Entry rules
MAX_ENTRY_ABOVE_PIVOT = 0.03  # NEW: max 3% above pivot or signal expires
EARNINGS_SAFETY_DAYS  = 10    # NEW: downgrade if results within 10 days

# Position sizing
RISK_PER_TRADE_PCT     = 2.0
MAX_POSITION_PCT       = 20.0
MIN_POSITION_PCT       = 2.0
MAX_PORTFOLIO_HEAT     = 6.0
MAX_SECTOR_CONC        = 30.0

# Drawdown circuit breaker
DRAWDOWN_HALVE_PCT  = 10.0
DRAWDOWN_CASH_PCT   = 20.0

# Exit rules (update after Test 7)
INITIAL_STOP_PCT    = 8.0
BREAKEVEN_AT_PCT    = 20.0
TRAIL_DAYS_40       = 10
TRAIL_DAYS_100      = 10
TIME_STOP_DAYS      = 20
CLIMAX_GAIN_PCT     = 20.0
CLIMAX_DAYS         = 15

# Rebalancing (update after Test 8)
REBALANCE_FREQ      = 'monthly'
RS_EXIT_THRESH      = 40

# Watchlist
MAX_WATCHLIST       = 20
PIPELINE_TRIGGER    = '16:15'
ALERT_TARGET        = '17:00'
```

---

## 7. Implementation Timeline

| Week | Task | Gate |
|------|------|------|
| 1 | Download 10yr NSE data + delivery + corp actions + FII | Data quality audit passes |
| 1–2 | Calculate all indicators including OBV | Unit tests all pass |
| 2 | Regime + crash indicator | Logic verified |
| 2–3 | Momentum ranking + vol scaling | Verified |
| 3 | Fundamental bonus scores + junk filter | Look-ahead verified |
| 3–4 | Earnings date safety + max entry rule | Logic verified |
| 4 | Trend template + VCP with OBV scope fix | Unit tests pass |
| 4–5 | Exit engine + portfolio risk | All exit rules tested |
| 5–7 | Backtest Tests 1–5 | Component gates pass |
| 7–9 | Backtest Tests 6–9 | Component gates pass |
| 9–11 | Backtest Test 10 (full system) | All 6 hard gates pass |
| 11–13 | Walk-forward (expanding + rolling) | OOS Sharpe gates pass |
| 13 | Update settings.py with proven parameters | All evidence-based |
| 13–15 | Streamlit dashboard + automation | Pipeline live 4:15pm |
| 15–27 | Paper trading — 3 months | All paper gates pass |
| 27 | **Go live — 25% capital** | All 12 gates passed |
| 27–31 | Performance tracker | All trades logged |
| 31–37 | FastAPI + PostgreSQL | API tested |
| 37–43 | Razorpay + tiers + React | Billing working |
| 43–51 | Zerodha auto-execution | 6 months validated |

---

*MomentumEdge Use Case Document v7.0 — Final*
*16 use cases | 15 database tables | 10 backtest tests | 3 validation phases*
*10-year backtest: Jan 2015 – Dec 2024 | 8 market cycles*

*Key changes v6→v7:*
*Delivery % removed from scoring (no evidence, operator contaminated)*
*OBV slope during base added — Granville 1963, 60yr track record*
*Smart institutional flow added — FII/DII/bulk deal based on promoter holding and sectoral caps*
*Earnings date safety rule added — prevents pre-results entries*
*Max entry 3% rule added — prevents chasing gaps*
*Rolling walk-forward added — stricter overfit test*
*OBV scope fixed — base period only, not full history*
*Test 9 added — scientifically validates OBV vs delivery %*

*Evidence: Jegadeesh & Titman 1993 | NSE Momentum 30 | Novy-Marx 2015*
*Barroso 2015 | Dierkes 2022 | Granville 1963 | He & Narayanamoorthy 2017*
*AQR QMJ | Baltussen 2026 (150yr, 46 countries)*
