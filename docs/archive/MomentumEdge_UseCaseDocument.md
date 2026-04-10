# MomentumEdge — Automated Indian Stock Scanning & Ranking System
## Use Case Document — MVP v1.0

| Field | Details |
|-------|---------|
| Version | 1.0 |
| Date | March 2026 |
| Status | Draft |
| Strategy | Minervini Trend Template + CANSLIM Momentum |
| Market | NSE India (End-of-Day Data) |
| Owner | Confidential |

---

## 1. Executive Summary

MomentumEdge is an automated end-of-day stock scanning and ranking system built exclusively for the Indian equity market (NSE). The system analyses all NSE-listed stocks after market close and generates a ranked watchlist of high-quality momentum breakout candidates every trading day.

The system combines three proven investment frameworks:

- **Mark Minervini's Trend Template** — ensures stocks are in a strong stage-2 uptrend before consideration
- **CANSLIM growth filtering** — selects only stocks with strong earnings, revenue, and institutional backing
- **Composite momentum ranking** — ranks survivors by multi-timeframe relative strength and proximity to 52-week highs

The MVP is designed for personal automated trading use, with a subscription SaaS product planned for Phase 2 offering tiered access to signals, research dashboards, and automated execution.

---

## 2. Target Market

### 2.1 Geographic Focus

- Phase 1 — India (Primary market, NSE-listed equities only)
- Phase 2 — Indian retail traders via subscription product
- Phase 3 — NRI investors and South Asian diaspora

### 2.2 Target Users

- Self-directed equity traders following momentum/growth strategies
- CANSLIM and Minervini-style traders seeking systematic screening
- Portfolio management services wanting systematic daily watchlists
- Subscription tier users wanting signals, alerts, and research

### 2.3 Market Context

- NSE has over 2,000 actively traded equities — manual screening is not scalable
- Indian retail participation in equities is growing 30%+ YoY
- No India-specific Minervini-style automated screening tool exists at scale
- Comparable global tools (MarketSmith, TC2000) do not cover NSE depth data

---

## 3. System Actors

### 3.1 Primary Actors

| Actor | Role |
|-------|------|
| Trader (Owner) | Uses the daily watchlist to make trading decisions on Zerodha Kite |
| Subscriber — Basic | Views the screening dashboard and receives alert signals |
| Subscriber — Pro | Full research dashboard with sector rankings and stock reports |
| Subscriber — Premium | All features plus auto-execution via their own Zerodha API key |

### 3.2 Secondary Actors

| Actor | Role |
|-------|------|
| Platform Administrator | Monitors pipeline health, manages users, handles billing |
| Support Staff | Handles subscriber queries and disputes |

### 3.3 System Actors

| System Actor | Function |
|-------------|----------|
| NSE Data Feed | Provides daily OHLCV, delivery, and index data via bhav copy |
| Fundamentals API (Screener.in / Tijori) | Provides EPS, revenue, ROE, and margin data |
| Zerodha Kite Connect API | Executes orders for Premium subscribers and the owner |
| PostgreSQL Database | Stores all price, fundamental, sector, and score data |
| Cron Scheduler | Triggers the pipeline automatically at 4:00 PM IST daily |
| Streamlit Dashboard | Serves the visual interface for all user tiers |
| Razorpay | Processes subscription payments (Phase 2) |
| WhatsApp / Email | Delivers daily signals and alerts to subscribers |

---

## 4. Core Use Cases

### UC-01: Daily Automated Data Ingestion

**Actor:** System (Cron Scheduler)
**Trigger:** 4:00 PM IST on every NSE trading day
**Precondition:** Market has closed. NSE bhav copy files are available for download.
**Postcondition:** Database updated with fresh OHLCV, delivery, and index data for all stocks.

**Main Flow:**
1. Cron job triggers the master pipeline script at 4:00 PM IST
2. System downloads NSE bhav copy (OHLCV data) for all listed stocks
3. System downloads NSE delivery data file for the day
4. System fetches Nifty 50 index closing data
5. System calls Fundamentals API for any updated quarterly data
6. System validates all downloaded data for completeness and integrity
7. System writes cleaned data to PostgreSQL database tables
8. System logs success and triggers Module 2 (Market Regime Engine)

**Alternative Flows:**
- A1: NSE server delay — system retries every 15 minutes up to 3 times
- A2: Data corruption detected — system sends error alert to admin and halts
- A3: Market holiday — system detects no bhav copy and skips gracefully

**Business Rules:**
- System must complete full pipeline before 6:00 PM IST to ensure timely signals
- Missing data for more than 5% of stocks triggers an admin alert
- All historical data is retained indefinitely for backtesting purposes

---

### UC-02: Market Regime Detection

**Actor:** System (Pipeline — Module 2)
**Precondition:** Daily data ingestion (UC-01) completed successfully.
**Postcondition:** Market regime classified as Bull, Neutral, or Bear. Exposure level set.

**Main Flow:**
1. System fetches current Nifty 50 price and its 200-day moving average
2. System calculates percentage of NSE stocks trading above their 50-day MA
3. System counts new 52-week highs vs new 52-week lows across the market
4. System applies classification rules to determine regime
5. System stores regime classification and passes exposure setting to scoring module

**Regime Classification:**

| Regime | Conditions | Exposure Setting |
|--------|-----------|-----------------|
| Bull | Nifty above 200MA + >60% stocks above 50MA + highs > lows | Aggressive — full watchlist |
| Neutral | Mixed conditions — 2 of 3 signals positive | Moderate — top 50% of scores only |
| Bear | Nifty below 200MA + <40% above 50MA + lows > highs | Defensive — cash recommended |

---

### UC-03: Sector Rotation Ranking

**Actor:** System (Pipeline — Module 3)
**Precondition:** Daily data ingestion complete.
**Postcondition:** Sectors ranked by momentum strength. Top 3 sectors flagged for stock prioritisation.

**Main Flow:**
1. System groups all stocks by sector classification
2. System calculates 6-month sector performance vs Nifty 50 benchmark
3. System counts stocks in each sector making new 52-week highs
4. System scores each sector and produces a ranked list
5. Top 3 sectors receive a priority multiplier in the composite stock score

---

### UC-04: Stock Momentum Ranking

**Actor:** System (Pipeline — Module 4)
**Precondition:** Price data updated. Nifty index data available for RS calculation.
**Postcondition:** Each stock assigned a momentum rank score (0–40).

| Momentum Factor | Calculation | Weight |
|----------------|------------|--------|
| 12-month momentum (excl. last month) | Price change over 12m minus last 1m | High |
| 6-month momentum | Price change over last 6 months | High |
| 3-month momentum | Price change over last 3 months | Medium |
| Relative strength vs Nifty 50 | Stock return minus Nifty return (6m) | High |
| Proximity to 52-week high | Current price / 52-week high | Medium |

---

### UC-05: CANSLIM Fundamental Filter

**Actor:** System (Pipeline — Module 5)
**Precondition:** Fundamentals data available from Screener.in or Tijori API.
**Postcondition:** Stocks failing fundamental thresholds eliminated. Passing stocks assigned fundamental score (0–25).

| Filter | Minimum Threshold | Disqualifies? |
|--------|------------------|---------------|
| Quarterly EPS growth (YoY) | >= 25% | Yes — below threshold eliminated |
| Revenue growth (YoY) | >= 20% | Yes — below threshold eliminated |
| Return on equity (ROE) | >= 15% | Yes — below threshold eliminated |
| Profit margin trend | Expanding over 3 quarters | Soft filter — score penalty |
| Debt-to-equity | < 1.0 preferred | Soft filter — score penalty |

---

### UC-06: Institutional Accumulation Detection

**Actor:** System (Pipeline — Module 6)
**Precondition:** Delivery percentage data and volume data available.
**Postcondition:** Stocks with institutional accumulation signals identified and scored.

**Accumulation Signals Detected:**
- Rising delivery percentage over the past 10 trading sessions
- Increasing volume on up-days vs decreasing volume on down-days
- Volume contraction during consolidation phases (VCP-style tightening)
- Market cap greater than ₹800 crore (institutional eligibility)
- Average daily traded value greater than ₹5 crore (liquidity filter)

---

### UC-07: Minervini Trend Template Screening

**Actor:** System (Pipeline — Module 7)
**Precondition:** At least 200 days of price history available for each stock.
**Postcondition:** Stocks not in a stage-2 uptrend eliminated from consideration.

All 6 conditions must be true for a stock to pass:

| Condition | Rule | Hard Filter? |
|-----------|------|-------------|
| Above 50-day MA | Current price > 50-day moving average | Yes |
| Above 150-day MA | Current price > 150-day moving average | Yes |
| Above 200-day MA | Current price > 200-day moving average | Yes |
| 50MA above 150MA | 50-day MA > 150-day MA | Yes |
| 150MA above 200MA | 150-day MA > 200-day MA | Yes |
| Near 52-week high | Current price within 25% of 52-week high | Yes |

---

### UC-08: Breakout Pattern Detection

**Actor:** System (Pipeline — Module 8)
**Precondition:** Stocks have passed Trend Template filter (UC-07).
**Postcondition:** Stocks with active breakout setups flagged with pattern type and score.

| Pattern | Detection Logic | Signal Strength |
|---------|----------------|----------------|
| Volatility Contraction (VCP) | Progressively tighter price swings over 3+ weeks with volume contraction | Very High |
| Tight consolidation base | Price range < 10% over 5+ weeks, volume drying up | High |
| Resistance breakout | Price breaks above prior pivot high on volume >= 1.5x average | High |
| Volume expansion breakout | Volume surge > 2x 50-day average on an up-day with price near highs | Medium |

---

### UC-09: Composite Scoring and Watchlist Generation

**Actor:** System (Pipeline — Modules 9 & 10)
**Precondition:** All module scores calculated. Market regime set.
**Postcondition:** Daily ranked watchlist generated and stored in database.

| Score Component | Max Points | Source Module |
|----------------|-----------|---------------|
| Momentum score | 40 | Module 4 |
| Fundamental score | 25 | Module 5 |
| Sector strength score | 20 | Module 3 |
| Technical structure score | 15 | Module 7 |
| Accumulation score | 15 | Module 6 |
| Liquidity / breakout score | 10 | Module 8 |
| **Total possible** | **125** | All modules |

**Watchlist Output Fields:**
- Stock symbol (NSE ticker)
- Composite score (0–125)
- Sector and sector rank
- Breakout signal status and pattern type
- Market regime at time of generation
- Suggested stop-loss level (based on base low)

---

### UC-10: Dashboard Access — Subscriber Views

**Actor:** Subscriber (Basic / Pro / Premium)
**Precondition:** User has active subscription. Daily pipeline has completed.
**Postcondition:** User views their tier-appropriate dashboard.

| Feature | Basic | Pro | Premium |
|---------|-------|-----|---------|
| Market regime indicator | ✅ | ✅ | ✅ |
| Top 10 watchlist stocks | ✅ | ✅ | ✅ |
| Full ranked watchlist (all scores) | ❌ | ✅ | ✅ |
| Sector rotation rankings | ❌ | ✅ | ✅ |
| Breakout pattern details | ❌ | ✅ | ✅ |
| Fundamental data per stock | ❌ | ✅ | ✅ |
| WhatsApp / email alerts | ❌ | ✅ | ✅ |
| Zerodha auto-execution | ❌ | ❌ | ✅ |
| Portfolio P&L tracking | ❌ | ❌ | ✅ |

---

### UC-11: Zerodha Auto-Execution (Premium)

**Actor:** Premium Subscriber
**Precondition:** Subscriber has connected their Zerodha Kite API key. Market regime is Bull.
**Postcondition:** Orders placed automatically based on watchlist signals.

**Main Flow:**
1. Subscriber navigates to Settings and connects their Zerodha Kite API key
2. Subscriber sets execution parameters: max position size, max stocks, stop-loss %
3. System detects breakout signal for a qualifying stock next morning at market open
4. System places a limit buy order via Kite API within subscriber's risk parameters
5. System simultaneously places a stop-loss order at the defined level
6. System notifies subscriber via WhatsApp of order placed and order ID

**Business Rules:**
- Auto-execution is disabled when market regime is Bear
- Maximum 5 open positions at any time (configurable by subscriber)
- Each subscriber's API key is encrypted and isolated — no cross-access possible
- Subscriber retains full control and can disable auto-execution at any time
- System is not a SEBI-registered advisor — subscribers execute at their own risk

---

### UC-12: Subscription Management and Billing

**Actor:** Subscriber, Razorpay (Phase 2)
**Precondition:** User has registered on the platform.
**Postcondition:** Subscription active and access granted to appropriate tier features.

| Tier | Price | Features |
|------|-------|----------|
| Basic | ₹499 / month | Screening dashboard, top 10 watchlist, regime indicator |
| Pro | ₹1,999 / month | Full watchlist, sector rankings, WhatsApp alerts, research data |
| Premium | ₹4,999 / month | All Pro features + Zerodha auto-execution + P&L tracking |

**Business Rules:**
- All tiers billed monthly via Razorpay with auto-renewal
- 7-day free trial available for Basic and Pro tiers
- No refunds after signals have been delivered for the month
- Annual subscription available at 20% discount

---

## 5. Database Design

| Table | Key Fields | Purpose |
|-------|-----------|---------|
| stocks | symbol, name, sector_id, market_cap, exchange | Master stock registry |
| price_data | symbol, date, open, high, low, close, volume | Daily OHLCV history |
| delivery_data | symbol, date, delivery_qty, delivery_pct | NSE delivery statistics |
| fundamentals | symbol, quarter, eps, revenue, roe, margin, pe | Quarterly financial data |
| sector_data | sector_id, sector_name, parent_sector | Sector classification |
| indicators | symbol, date, ma50, ma150, ma200, rs_score, atr | Calculated indicators |
| scores | symbol, date, momentum_score, fundamental_score, composite_score | Daily scoring results |
| watchlist | date, symbol, composite_score, pattern_type, regime | Daily watchlist output |
| users | user_id, email, tier, api_key_encrypted, created_at | Subscriber accounts |
| orders | order_id, user_id, symbol, qty, price, status, kite_id | Execution log |

---

## 6. Technical Architecture

### 6.1 Phase 1 — MVP (Local)

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Data ingestion | Python — requests, pandas | Download and clean NSE data |
| Database | SQLite (local) | Store all price and score data |
| Calculations | Python — pandas, numpy, ta library | All indicators and scores |
| Scheduler | Windows Task Scheduler / cron | Run pipeline at 4 PM IST |
| Dashboard | Streamlit (localhost) | Visual watchlist interface |
| Broker API | Zerodha Kite Connect | Manual order execution |

### 6.2 Phase 2 — Cloud Deployment

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Server | Hetzner CX21 or DigitalOcean Droplet | 24/7 pipeline execution |
| Database | PostgreSQL | Production-grade data storage |
| Scheduler | Linux cron | Automated daily pipeline trigger |
| Web server | Nginx (reverse proxy) | Route traffic to Streamlit |
| SSL | Let's Encrypt (free) | HTTPS for dashboard domain |
| Monitoring | Email / Telegram alerts | Pipeline failure notifications |

### 6.3 Phase 3 — Subscription Product

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend API | FastAPI (Python) | User auth, tier access, order routing |
| Database | PostgreSQL with user tables | Multi-user data isolation |
| Payments | Razorpay | Indian subscription billing |
| Alerts | Twilio WhatsApp API / Interakt | Signal delivery to subscribers |
| Frontend | React.js | Professional subscriber dashboard |
| Auth | JWT tokens | Secure session management |
| Hosting | AWS / DigitalOcean | Scalable production environment |

---

## 7. Automation Pipeline — Module 11

The master pipeline runs every trading day at 4:00 PM IST in the following sequence:

| Step | Module | Action | Est. Time |
|------|--------|--------|----------|
| 1 | M1 | Download NSE bhav copy + delivery data | 2 min |
| 2 | M1 | Update PostgreSQL database tables | 2 min |
| 3 | M4 + M7 | Calculate all moving averages and indicators | 5 min |
| 4 | M2 | Detect market regime | 1 min |
| 5 | M3 | Rank sectors by momentum | 2 min |
| 6 | M5 | Apply CANSLIM fundamental filters | 2 min |
| 7 | M6 | Score institutional accumulation signals | 2 min |
| 8 | M7 | Apply Minervini trend template filter | 2 min |
| 9 | M8 | Detect breakout patterns (VCP, base, breakout) | 3 min |
| 10 | M9 | Calculate composite scores for all stocks | 2 min |
| 11 | M10 | Generate and store daily watchlist | 1 min |
| 12 | M12 | Refresh dashboard data | 1 min |
| 13 | M11 | Send WhatsApp / email alerts (Phase 2+) | 1 min |

Total pipeline runtime: approximately 25–30 minutes. Dashboard updated by 4:30 PM IST.

---

## 8. Non-Functional Requirements

### 8.1 Performance
- Daily pipeline must complete within 60 minutes of trigger
- Dashboard must load within 3 seconds for any user
- WhatsApp alerts delivered within 5 minutes of pipeline completion

### 8.2 Reliability
- Pipeline must have automatic retry logic for data download failures
- System must detect market holidays and skip gracefully
- Error alerts must be sent to admin if pipeline fails
- All data must be backed up daily to prevent loss

### 8.3 Security
- All Zerodha API keys encrypted at rest using AES-256
- Each subscriber's API key is completely isolated from others
- Dashboard access protected by authentication (Phase 2)
- HTTPS enforced for all web traffic

### 8.4 Compliance
- System generates signals and screening output — not SEBI-registered investment advice
- Subscribers execute trades using their own Zerodha accounts and bear full trading risk
- Subscription product to be reviewed by legal counsel before public launch
- All user data stored in compliance with Indian IT Act and DPDP Bill

---

## 9. Success Metrics

### 9.1 System Performance Metrics

| Metric | Target |
|--------|--------|
| Pipeline reliability | > 99% successful runs on trading days |
| Signal accuracy (breakouts that work) | > 50% of signals achieve > 10% gain before stop |
| Watchlist quality | Top 20 stocks outperform Nifty 50 over rolling 3 months |
| Dashboard uptime | > 99.5% availability |
| Pipeline completion time | < 60 minutes after 4 PM trigger |

### 9.2 Business Metrics (Phase 2+)

| Metric | Year 1 Target |
|--------|--------------|
| Total subscribers | 500 paid subscribers |
| Basic tier subscribers | 300 |
| Pro tier subscribers | 150 |
| Premium tier subscribers | 50 |
| Monthly recurring revenue (MRR) | ₹8–12 lakh |
| Free trial to paid conversion | > 25% |
| Monthly subscriber churn | < 8% |

---

## 10. Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| NSE data source changes or goes down | High | Build fallback to Yahoo Finance / alternative sources |
| Fundamentals API rate limiting or cost increase | Medium | Cache quarterly data aggressively — only fetch on update |
| Zerodha Kite API changes or downtime | High | Auto-execution has manual override; alerts still work without it |
| SEBI scrutiny of signal subscription product | High | Legal review before Phase 2 launch; position as software tool not advice |
| Strategy underperforms in bear market | Medium | Market regime filter auto-reduces exposure in bear conditions |
| Server downtime during market hours | Medium | Auto-restart scripts; admin alert via SMS within 5 minutes |
| Data quality issues (bad prices / splits) | High | Corporate action adjustment logic; data validation checks on ingestion |

---

## 11. Development Roadmap

| Phase | Duration | Deliverables |
|-------|----------|-------------|
| Phase 1 — MVP | 4–6 weeks | All 13 Python modules, SQLite DB, Streamlit dashboard, local automation |
| Phase 2 — Cloud | 2–3 weeks | PostgreSQL migration, Hetzner deployment, cron automation, domain + SSL |
| Phase 3 — Beta | 3–4 weeks | 10 beta users, feedback iteration, signal accuracy tracking |
| Phase 4 — Subscription | 4–6 weeks | FastAPI backend, Razorpay billing, user auth, tiered access, WhatsApp alerts |
| Phase 5 — Auto-execution | 3–4 weeks | Zerodha Kite integration for Premium tier, order management, P&L tracking |

---

## 12. Appendix

### 12.1 Glossary

| Term | Definition |
|------|-----------|
| CANSLIM | William O'Neil's growth stock framework: Current earnings, Annual earnings, New products, Supply/demand, Leader, Institutional support, Market direction |
| VCP | Volatility Contraction Pattern — Mark Minervini's base pattern with progressively tightening price swings |
| Trend Template | Minervini's 6-condition filter requiring a stock to be in a confirmed stage-2 uptrend |
| Relative Strength (RS) | A stock's price performance relative to the Nifty 50 index over a given period |
| Bhav Copy | NSE's end-of-day file containing OHLCV data for all listed securities |
| Delivery % | The percentage of traded shares that resulted in actual delivery (vs. intraday). High delivery = strong conviction |
| Stage 2 | Mark Minervini's term for the advancing/uptrend phase of a stock's price cycle |
| MRR | Monthly Recurring Revenue — total subscription revenue per month |
| Kite Connect | Zerodha's official API for programmatic trading |

### 12.2 Subscription Tier Comparison

| Feature | Basic (₹499) | Pro (₹1,999) | Premium (₹4,999) |
|---------|-------------|-------------|----------------|
| Market regime indicator | ✅ | ✅ | ✅ |
| Daily watchlist (top 10) | ✅ | ✅ | ✅ |
| Full ranked watchlist | ❌ | ✅ | ✅ |
| Composite score per stock | ❌ | ✅ | ✅ |
| Sector rotation rankings | ❌ | ✅ | ✅ |
| Breakout pattern details | ❌ | ✅ | ✅ |
| Fundamental data per stock | ❌ | ✅ | ✅ |
| WhatsApp / email alerts | ❌ | ✅ | ✅ |
| Historical watchlist archive | ❌ | ✅ | ✅ |
| Zerodha auto-execution | ❌ | ❌ | ✅ |
| Portfolio P&L tracking | ❌ | ❌ | ✅ |
| Custom risk parameters | ❌ | ❌ | ✅ |
| Priority support | ❌ | ❌ | ✅ |

---

*End of Use Case Document — MomentumEdge v1.0 | Confidential*
