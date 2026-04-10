# UniPro AI — MomentumEdge System Use Case v16.0
**NSE Mid-Cap Momentum Platform — Complete Institutional Operating System**

| Field | Value |
|---|---|
| Document Version | 16.0 |
| Date | March 2026 |
| Status | Final — Implementation Ready |
| Backtest Period | January 2010 – December 2022 (OOS: 2023–2024 LOCKED) |
| Validated Against | 40 NSE stocks 2020–2025 \| Exit Simulation: Force Motors 8.8x (+160% vs old 7.2x), Himadri blended exit improvement \| GE Vernova T&D 2020–2024 full simulation validated |
| Licence Architecture | SEBI RA → AIF Category III → PMS — all layers pre-built, activate by phase |

---

## Evidence Base

| Reference | Finding |
|---|---|
| Jegadeesh & Titman 1993 | Momentum works; optimal holding period 6–12 months |
| Baltussen et al. 2026 | 150 years, 46 countries, momentum universal |
| NSE Nifty200 Momentum 30 | 19.06% CAGR (note: Nifty200 membership = implicit quality filter) |
| Barroso & Santa-Clara 2015 | Volatility scaling materially improves momentum Sharpe and reduces crash risk |
| Dierkes & Krupski 2022 | Momentum crash conditions framework (thresholds India-calibrated in Test 3) |
| Granville 1963 | OBV concept (practitioner-validated; limited peer-reviewed evidence — validated in Test 9) |
| He & Narayanamoorthy 2017 | Earnings acceleration predicts abnormal returns |
| Grinblatt & Moskowitz 2004 | Consistent winners have strongest subsequent returns (hold signal) |
| Lakonishok & Lee 2001 | Insider buying predicts returns (proxy for promoter buying signal) |
| AQR QMJ | Quality alongside momentum; momentum rank decay = primary exit signal |
| López de Prado 2014 | Parameter reduction, Deflated Sharpe Ratio |
| Bailey et al. 2014 | Probability of Backtest Overfitting (CSCV method) |
| Lesmond, Schill & Zhou 2004 | Momentum profits may be illusory after transaction costs (validates Test 15 importance) |
| Chan, Jegadeesh & Lakonishok 1996 | Earnings revision momentum predicts returns. SUE proxy bonus (Bonus 9) implements this finding using eps_growth_yoy as the surprise measure. |
| **Bernard & Thomas 1989** | **Post-earnings announcement drift (PEAD) is driven by the earnings surprise itself — not by analyst consensus specifically. YoY EPS growth is a valid SUE proxy. Justifies `calculate_sue_proxy_bonus()` using Screener.in data with 100% universe coverage.** |
| **Moskowitz & Grinblatt 1999** | **"Do Industries Explain Momentum?" — sector momentum accounts for a large portion of individual stock momentum. Justifies UC-04 Step 0 daily sector ranking calculation and the sector bonus/penalty scoring.** |
| **Bessembinder 2018** | **Top 4% of stocks drive all net stock market wealth creation. Extreme positive skewness in individual stock returns reinforces the necessity of Phase 4 loose exit rules and the Monster Stock Detection Layer — cutting monster runs early destroys the majority of realised alpha.** |
| Novy-Marx 2015 | "Fundamentally, momentum is relative strength" — price momentum IS fundamental momentum lagged. Cited in v7 evidence base. Dropped from v16 active citations because the SUE proxy bonus (Bernard & Thomas 1989 + Chan et al. 1996) covers the same mechanism more precisely and with better OOS evidence. Novy-Marx finding does not contradict any v16 rule — it was superseded by a more specific citation. Retain in institutional background reading. |

---

## Changes v15 → v16

---

## Known Discrepancies vs v7 — Resolved (March 2026 Audit)

The following differences between the earlier v7 specification and v16 were identified and resolved in a March 2026 audit. Each is documented with its resolution and rationale.

### Flaw 1 — OOS Methodology (High-Stakes Risk — Acknowledged)

**v7:** Backtest period Jan 2015–Dec 2024 (10 years, includes 2023–2024 in-sample). Results looked good across a longer period but 2023–2024 were used during development, making them contaminated.

**v16:** Backtest 2010–2022 (13 years). 2023–2024 strictly locked as OOS — never viewed during design. Methodologically correct.

**Risk acknowledged:** If the single OOS reveal (Test 14) fails, there is no fallback. The entire system must be redesigned from scratch. This is the right tradeoff — a contaminated test is not actually a test — but it is a high-stakes decision that Mohit must consciously accept before locking OOS. Once locked, it cannot be undone.

**Resolution:** Accept the risk. The OOS lock is non-negotiable for statistical validity. The backtest period 2010–2022 includes 4 distinct market regimes (2010–2014 post-GFC recovery, 2015–2016 bear, 2018 correction, 2020–2022 COVID + bull) which is sufficient diversity. Do not extend BACKTEST_END to 2024 under any circumstances.

---

### Flaw 2 — Go-Live Capital: v7 Said 25%, v16 Says 10%

**v7:** Go-live at 25% of intended capital immediately.

**v16:** Go-live at 10%, scale to 25% only after 3 months live validation with both win rate and correlation conditions met.

**Resolution:** v16 is correct. v7 was aggressive. The change is intentional and documented here to prevent confusion if reading both documents. 10% initial deployment is the right discipline — it limits damage if a bug or regime bias that paper trading did not catch surfaces in live trading. The change log below captures this.

---

### Flaw 3 — Liquidity Threshold: ₹10cr vs ₹15cr (ACTIVE AUDIT — FIX BEFORE CODING)

**v7:** ₹15 crore minimum daily traded value. Hard-coded as a locked value.

**v16:** ₹10 crore minimum, marked `[FREE]` — test 10 / 15 / 20 in Test 2.

**Why the discrepancy exists:** v7 locked ₹15cr based on a position sizing argument: a Rs 5 lakh position in a ₹10cr ADV stock is 0.5% of daily volume and may create slippage. v16 set ₹10cr as the starting default for Test 2 to see whether the range 10–20 is material.

**Correct approach:** Neither is wrong until Test 2 runs. But ₹10cr is borderline for any position above Rs 2 lakh. The ₹15cr threshold from v7 is the safer starting default before backtesting confirms otherwise.

**ACTION REQUIRED BEFORE CODING:** Set `MIN_DAILY_TRADED_VALUE_CR = 15` as the starting default in settings.py. If Test 2 shows 10 produces materially better Calmar than 15, lower it. If 15 and 10 are within 5% of each other, keep 15 for safety margin. Do not use 10 as the unquestioned default without running Test 2 first. Add a comment to settings.py noting this audit finding.

```python
# AUDIT NOTE (March 2026): v7 used ₹15cr (locked). v16 initially set ₹10cr.
# Starting default set to ₹15cr pending Test 2 confirmation.
# If Test 2 shows ₹10cr Calmar within 5% of ₹15cr: keep ₹15cr for safety.
# Only lower to ₹10cr if Test 2 shows material alpha at lower threshold.
MIN_DAILY_TRADED_VALUE_CR  = 15   # [FREE] test 10 / 15 / 20 in Test 2
```

---

### Flaw 4 — Paper Trading Period: v7 Said 3 Months, v16 Says 6 Months

**v7:** Paper trading 3 months (Week 15–27).

**v16:** Paper trading 6 months minimum (120 trading days, Week 19–43).

**Resolution:** v16 is more rigorous and correct. 3 months captures only one quarterly earnings cycle. 6 months captures two cycles, includes a broader range of market conditions, and gives more confidence in live vs paper correlation. The 3-month timeline in v7 was optimistic. If you were planning your launch timeline based on v7, add 3 months.

---

### Flaw 5 — Complexity Risk: Task Split Undefined

**Problem:** v16 has 40 use cases, 26+ tables, 16 backtest tests, and multiple operational systems. It is being built by one non-coder (Mohit) and one remote ML developer (friend, limited availability). There is no explicit task assignment for who builds what.

**Resolution:** The following task split is now the official build assignment:

**Developer builds (everything Python, database, pipeline):**
- UC-01 through UC-17: all data ingestion, scoring, signal generation, exit engine, regime engine, dashboard
- UC-36 through UC-37: pipeline monitoring and checkpoint recovery
- UC-18 through UC-19: daily and weekly reports (plain text generation only)
- Database schema: all 26+ tables, immutable audit triggers
- settings.py: all parameters as specified
- All 16 backtest tests + walk-forward + go-live gate checks

**Mohit manages (no coding required):**
- Screener.in Premium subscription and API credentials
- NSE API access and data download scripts (developer writes the script, Mohit runs it)
- Zerodha account setup and Kite Connect API credentials
- Paper trading execution review (review dashboard, not code)
- All SEBI compliance actions (lawyer, registration, documentation)
- All client-facing decisions (pricing, communication, onboarding)

**Activate only after SEBI RA registration (Phase 2 — developer activates existing code):**
- UC-23 through UC-30: client management, compliance calendar, disclaimer automation
- UC-20, UC-21: client-facing reports
- UC-34, UC-35: order management system, execution quality (Month 18+ with Kite Connect)

**Activate only after AIF/PMS licence (Phase 5):**
- UC-31 through UC-33: NAV engine, fee calculation, investor allocation

**Do not build yet (future phases):**
- UC-24: client portal (SaaS, Phase 4)
- UC-38, UC-39, UC-40: advanced ops (Phase 3, build only after 3 months live)

**Single most important rule for the developer:** Build UC-01 to UC-14 first. Get paper trading running before building anything in UC-15 onwards. A perfect compliance stack running on a broken signal engine is worthless.

---

### Flaw 6 — Screener.in Data Gap: No Fallback Documented

**Problem:** If Screener.in data is missing for a specific mid-cap stock (patchy data quality in smaller names), the SUE proxy bonus, OCF hard block, pledge hard block, D/E penalty, and multiple other signals all fail silently. The system may include or exclude stocks based on data absence rather than data content.

**Resolution:** The following fallback rules are now added to UC-04 Step 1 (hard filters) and UC-04 Step 2 (composite scoring):

```python
def handle_missing_fundamentals(symbol, as_of_date, fundamentals):
    """
    Screener.in data gap fallback rules.
    
    If fundamentals is None or empty:
      - EXCLUDE from universe (fail Block 6 by default)
      - Log to data_quality_alerts with severity='CRITICAL'
        reason='screener_missing_all'
      - Alert developer immediately (WhatsApp)
      - Do NOT silently pass the stock with zero bonuses
    
    If specific fields are missing within a fundamentals record:
      - eps missing: Block 6 cannot be evaluated → exclude
        severity='CRITICAL', alert_type='screener_missing_field'
      - ocf_cr missing: Block 7 cannot be evaluated → exclude
        severity='CRITICAL', alert_type='screener_missing_field'
      - promoter_pledge_pct missing: Block 8 cannot be evaluated → exclude
        severity='CRITICAL', alert_type='screener_missing_field'
        (BSE shareholding XML fallback attempted first — see Section 3.5)
      - eps_growth_yoy missing: SUE bonus = 0, no exclusion
        severity='WARNING', alert_type='screener_missing_field'
      - revenue_cr missing: revenue/margin bonus = 0, no exclusion
        severity='WARNING', alert_type='screener_missing_field'
      - debt_to_equity missing: D/E signals = 0, no exclusion
        severity='INFO', alert_type='screener_missing_field'
      - expected_result_date missing: earnings safety window = ACTIVE for 30 days
        (assume earnings may be imminent — conservative)
        severity='WARNING', alert_type='screener_missing_field'
    
    CRITICAL: Hard block fields (eps, ocf, pledge) → missing = exclude.
              Bonus/penalty fields → missing = 0 (no signal, no block).
              Never assume a missing value is safe.
    
    After CRITICAL exclusion:
      - Trigger Screener.in re-fetch for that symbol (automated)
      - If data still missing after 3 daily re-fetch attempts:
          Add to data_quality_alerts with resolved=False
          Pipeline step 3 will halt after 24h if CRITICAL unresolved
          Mohit reviews; decides if BSE direct filing is sufficient fallback
    """
    if not fundamentals:
        log_data_quality_alert(
            symbol        = symbol,
            alert_type    = 'screener_missing_all',
            severity      = 'CRITICAL',
            detail        = f'No Screener.in fundamentals found as of {as_of_date}',
            as_of_date    = as_of_date
        )
        send_whatsapp(DEV_PHONE,
            f"DATA GAP CRITICAL: {symbol} — no Screener.in fundamentals "
            f"as of {as_of_date}. Stock excluded from universe until resolved. "
            f"Auto re-fetch triggered. Check data_quality_alerts table."
        )
        trigger_screener_refetch(symbol)
        return False, 'screener_data_missing'

    # Check critical hard-block fields individually
    latest = fundamentals[0]
    critical_fields = ['eps', 'ocf_cr', 'promoter_pledge_pct']
    for field in critical_fields:
        if latest.get(field) is None:
            # Pledge: attempt BSE XML fallback before excluding
            if field == 'promoter_pledge_pct':
                bse_pledge = fetch_bse_shareholding_pledge(symbol, as_of_date)
                if bse_pledge is not None:
                    latest['promoter_pledge_pct'] = bse_pledge
                    log_data_quality_alert(
                        symbol=symbol, alert_type='screener_missing_field',
                        severity='INFO', missing_field=field,
                        detail=f'Pledge sourced from BSE XML fallback: {bse_pledge}%',
                        as_of_date=as_of_date
                    )
                    continue   # resolved via BSE — do not exclude
            log_data_quality_alert(
                symbol=symbol, alert_type='screener_missing_field',
                severity='CRITICAL', missing_field=field,
                detail=f'Hard block field {field} missing — stock excluded conservatively',
                as_of_date=as_of_date
            )
            trigger_screener_refetch(symbol)
            return False, f'screener_field_missing_{field}'

    return True, None
```

**BSE fallback for hard block fields:** If Screener.in is missing pledge data specifically, cross-check BSE shareholding XML directly (Source 2, Section 3.5). If BSE XML also has no data, exclude the stock. Never assume pledge is zero when the data is absent.

---

### Flaw 7 — Version Change Log: v7 → v16 Key Differences Summary

For anyone who read v7 and is now implementing v16, these are the differences that will affect your planning:

| Parameter | v7 | v16 | Direction |
|---|---|---|---|
| Backtest period | 2015–2024 | 2010–2022 | More rigorous |
| OOS period | None (all in-sample) | 2023–2024 locked | More rigorous |
| Go-live capital | 25% immediately | 10% → 25% after 3 months | More conservative |
| Paper trading | 3 months | 6 months | More rigorous |
| Liquidity threshold | ₹15cr locked | ₹15cr default [FREE] Test 2 | Audit pending |
| Use cases | 16 | 40 | Larger scope |
| Backtest tests | 10 | 16 + Fold 8 + Test 7H | More rigorous |
| 40-stock validation | None | Complete, named | More rigorous |
| Compliance stack | None | Full SEBI RA + AIF/PMS | Added |
| Screener.in fallback | Not documented | Now documented (Flaw 6 fix above) | Fixed |
| Novy-Marx 2015 | In evidence base | Superseded by Bernard & Thomas + Chan et al. | Explained |

---

### 1 Targeted Alpha Enhancement — Earnings Turnaround Watch

**Origin:** GE Vernova T&D India 2020–2024 full backtest simulation. System entered at ₹350–₹380 in late 2023. Analysis confirmed the stock was available at ₹220–₹240 in June–July 2023 but EPS hard block was still active (Q1 FY24 results not yet announced). Option C closes this gap by giving Mohit advance warning 1–3 quarters before the entry signal fires.

**Full 40-stock validation of this change:**
- Correctly avoided traps (Cosmo Ferrites, Websol, Megasoft, Servotech, Mercury EV, Magellanic, SPEL): all have Turnaround Watch fire BUT existing hard blocks (pledge, OCF, SEBI fine, business pivot) prevent any entry. **Zero false entries.**
- Main system catches: 29 of 40 completely unaffected. Force Motors, JBM Auto, Shakti Pumps, V2 Retail: minor 1–2 month earlier awareness via Turnaround Watch.
- GE Vernova T&D: Turnaround Watch fires at ₹220 (June 2023). Entry signal fires September–October 2023 at ₹280–₹320 vs current ₹350–₹380. **+₹60–₹70 per share improvement.**
- No other stock in the 40-stock universe has its entry price materially changed.

**What was rejected (documented):**
- Option B (Corporate Restructuring Promoter Selling Exception): rejected for v16. Full 40-stock check confirmed GE Vernova T&D's promoter holding was stable at 75% in mid-2023 — the selling started in 2024–2025 post GE Vernova spinoff. Option B was not the binding constraint. Option C alone closes the gap. Option B reserved for v17 if a clear live-trading candidate emerges.

**The change:**

1. **[ALPHA] `check_earnings_turnaround()` — NEW UC-04 Step 0B** — fires when a company transitions from loss-making back to first confirmed profitable quarter after ≥4 quarters of improving EPS trajectory. Adds stock to Turnaround Watch panel. Not a buy signal. Defines the entry trigger condition for Mohit to monitor. Dashboard alert fires with expected entry price range.

2. **[DASHBOARD] Turnaround Watch panel — NEW UC-17 addition** — separate panel below pre-profit watchlist. Shows stocks where EPS has turned positive after a loss phase and entry signal is expected within 1–3 quarters. Clearly labelled "MONITORING ONLY — hard blocks still active — no entry until Tier 1/2 signal fires."

3. **[PIPELINE] Pipeline step 12a added** — `run_turnaround_watch_scan()` runs daily after exit cascade check. Scans eligible universe candidates approaching EPS block clearance.

4. **[SETTINGS] 4 new parameters** — `TURNAROUND_EPS_IMPROVEMENT_QTRS`, `TURNAROUND_MIN_REVENUE_GROWTH`, `TURNAROUND_HISTORY_QTRS`, `TURNAROUND_ALERT_ENABLED`.

5. **[RISK] Fast crash vs monster override conflict resolved** — UC-03D now explicitly states: fast crash halves ALL positions including Phase 4 monster cores. `monster_override_active` flag is NOT cleared — Phase 4 rules resume automatically on reset. Risk management always takes priority over alpha management during crash events.

6. **[SCHEMA] `suppression_reason VARCHAR(50)` added to `turnaround_watch` table** — logs exactly which hard block caused suppression (pledge_pct / sebi_fine_24m / business_pivot / ocf_negative / multiple). One-glance audit trail clarity. `consecutive_pos_eps` counter added — resets if EPS dips negative again, flagging broken turnaround thesis.

7. **[OMS] Pre-trade block in UC-34 `place_order()`** — technically enforces Turnaround Watch monitoring-only discipline. If Mohit attempts manual entry on a watch stock before Tier 1/2 signal fires: order is BLOCKED, WhatsApp alert sent, attempt logged in `blocked_order_attempts` table (immutable, SEBI audit trail). `OrderBlockedError` raised. Cannot be bypassed.

---

## Changes v14 → v15

### Complete Institutional Operating System — 23 New Use Cases Across 6 Layers

v15 completes the full institutional stack. Every use case is built once and activated by phase as licences are obtained. No rebuilding. No rework.

**Activation phases:**
- `[PHASE 1]` — Paper trading (build now, activate immediately)
- `[PHASE 2]` — SEBI RA registration (activate on licence grant)
- `[PHASE 3]` — Go-live / live trading (activate at Week 43)
- `[PHASE 4]` — SaaS launch (activate at 500+ subscribers)
- `[PHASE 5]` — AIF/PMS licence (activate on licence grant)

**Layer 1 — Reporting (5 use cases)**

1. **UC-18 [PHASE 1]** Daily Operations Report — auto-generated 5:00 PM IST every trading day. Pipeline health, current risk, open alerts, regime status. Archived daily. WhatsApp + email delivery.

2. **UC-19 [PHASE 1]** Weekly Review Report — auto-generated every Friday 5:30 PM IST. Signal quality, portfolio attribution, regime narrative, forward earnings calendar. All 18 UC-15 review questions answered with live data. Markdown + PDF.

3. **UC-20 [PHASE 2]** Monthly Client Report — two versions (internal full + external SEBI-compliant). Performance vs benchmark, top holdings, strategy commentary, risk metrics. PDF delivered to Pro/Institutional subscribers.

4. **UC-21 [PHASE 3]** Quarterly Attribution Report — full signal attribution, factor decomposition, strategy decay check, parameter stability. Internal only.

5. **UC-22 [PHASE 5]** Annual Strategy Review — full system audit, evidence base review, parameter re-optimisation review, regulatory review. Structured manual process with auto-generated data package.

**Layer 2 — Client Management (4 use cases)**

6. **UC-23 [PHASE 2]** Client Onboarding — KYC, risk profiling, risk disclosure document (SEBI mandated), agreement signing, tier assignment. Digital workflow.

7. **UC-24 [PHASE 4]** Client Portal — each subscriber logs in to see their tier's signals, their P&L (if using system), regime status, earnings alerts. Tier-gated content delivery.

8. **UC-25 [PHASE 2]** Research Delivery Engine — every signal delivered to clients as a formal research note with SEBI-mandated disclaimer, timestamp, analyst registration number, risk disclosure. Stored with full audit trail.

9. **UC-26 [PHASE 2]** Client Communication Archive — every communication (WhatsApp, email, portal message) logged with timestamp, content, client ID. 5-year retention as required by SEBI. Searchable.

**Layer 3 — Compliance (4 use cases)**

10. **UC-27 [PHASE 2]** Compliance Calendar — auto-tracks all SEBI filing deadlines, RA renewal dates, client disclosure requirements, audit schedules. Alerts 30/14/7/1 days before each deadline.

11. **UC-28 [PHASE 2]** Personal Trading Restriction Engine — Mohit's personal trades cannot execute in the same stock within 30 days before or after a client recommendation. System auto-flags conflicts. SEBI RA Chinese wall requirement.

12. **UC-29 [PHASE 2]** SEBI Audit Trail — all research, all signals, all client communications, all trades — immutable log with timestamps. 5-year retention. Exportable for SEBI inspection. Never deletable.

13. **UC-30 [PHASE 2]** Disclaimer Automation — every client-facing output (signal, report, WhatsApp, email) auto-appends the correct SEBI-mandated disclaimer with RA registration number. No manual disclaimer required. Disclaimer text versioned and updated when SEBI rules change.

**Layer 4 — Fund Operations (3 use cases)**

14. **UC-31 [PHASE 5]** NAV Calculation Engine — daily NAV per unit for AIF/PMS. Accounts for unrealised P&L, accrued fees, dividends, corporate actions. Published daily to investors.

15. **UC-32 [PHASE 5]** Fee Calculation Engine — management fee (annual % of AUM, accrued daily), performance fee (% of profits above hurdle rate, with high watermark). Auto-calculates and logs. Never charges below high watermark.

16. **UC-33 [PHASE 5]** Investor Capital Allocation — tracks each investor's units, entry NAV, current NAV, unrealised P&L, accrued fees, redemption requests. Reconciles daily with custodian.

**Layer 5 — Execution Infrastructure (2 use cases)**

17. **UC-34 [PHASE 3]** Order Management System — queue, route, track, and confirm all orders. Handles partial fills. Stores actual fill vs signal price for slippage attribution. Zerodha Kite Connect integration.

18. **UC-35 [PHASE 3]** Execution Quality Report — daily slippage analysis (actual fill vs next-day open assumption). VWAP comparison for larger orders. Market impact measurement. Flags when slippage exceeds 0.5% assumption consistently.

**Layer 6 — Technology Operations (3 use cases)**

19. **UC-36 [PHASE 1]** Pipeline Monitoring and Alerting — every pipeline step logs completion time and status. If any step fails or exceeds 2× expected time: immediate WhatsApp alert to Mohit and developer. No silent failures.

20. **UC-37 [PHASE 1]** Checkpoint and Recovery System — each pipeline step writes a checkpoint to `pipeline_log` table on completion. If pipeline crashes and restarts: resumes from last completed checkpoint, not from step 1. Critical for data integrity.

21. **UC-38 [PHASE 3]** Environment Management — three separate environments: DEV (developer testing), PAPER (paper trading with live data), LIVE (real capital). Separate databases. Settings.py has `ENVIRONMENT` flag. No accidental cross-contamination.

**Layer 7 — Business Intelligence (2 use cases)**

22. **UC-39 [PHASE 3]** Strategy Decay Detection — weekly statistical test comparing live win rate, average win/loss, and Sharpe against the backtest distribution. If live performance diverges beyond 2 standard deviations for 4 consecutive weeks: auto-alert "STRATEGY DECAY WARNING" with data. Forces a systematic review before continuing.

23. **UC-40 [PHASE 3]** Signal Quality Trends — rolling 90-day win rate per signal type (VCP, tight base, breakout), per tier (1/2/3), per sector, per regime. Dashboard panel showing which signals are working live and which are degrading. Early detection of market structure changes.

---

## Changes v13 → v14

### 7 Implementation Completeness, Data Architecture and Alpha Fixes

1. **[DATA]** Stock-to-sector mapping locked — NSE official sector classification (22 broad sectors). Section 3.0 added. Fixes the last undefined structural input in the system. All sector bonus/penalty, sector rankings, sector concentration cap, and monster score sector rank now draw from a single defined source: `nseindia.com/api/equity-master`. Sector level (22 groups) used — not sub-industry (80 groups) which has too few members per bucket for reliable median calculation.

2. **[DATA]** BSE cross-validation and future expansion architecture — Section 3.7 added. Current use: BSE bhav copy for daily price cross-check (`cross_check_bse_nse()`, divergence > 0.5% flagged). BSE corporate actions as early-warning check. BSE shareholding XML for promoter pledge cross-validation. Future use: `exchange` column added to `price_data` PRIMARY KEY. `bse_code` added to `stocks` table. ISIN is the definitive cross-reference between NSE and BSE. Schema is BSE-ready with zero rework when full expansion is triggered. BSE expansion trigger: material alpha in BSE-only mid-cap listings OR universe expansion below ₹1,000cr. UC-01 steps 6a and 6b added for daily BSE cross-validation.

3. **[ALPHA]** Explicit sector ranking calculation — `calculate_sector_rankings()` function added as UC-04 Step 0. Sectors ranked daily by equal-weighted median 3-month momentum of NSE-classified member stocks. Rank 1 = strongest sector. Output feeds sector bonus/penalty in `build_composite_score()`. Previously sector rank was passed as a parameter but never defined or computed — missing implementation definition now fixed. New table: `sector_rankings`. Updated daily at pipeline Step 13a. Moskowitz & Grinblatt 1999 added to evidence base table.

4. **[ALPHA]** Post-earnings drift — `calculate_sue_proxy_bonus()` using `eps_growth_yoy` (Screener.in, 100% universe coverage, zero new data source). Replaces original analyst-estimate design — Screener.in does not provide `analyst_estimate_eps`. Evidence: Bernard & Thomas 1989 + Chan, Jegadeesh & Lakonishok 1996. `PEAD_ENABLED = True` in settings; set False if Test 5 shows no OOS alpha. Thresholds: eps_growth_yoy > 50% = +10, > 25% = +6, < −20% = −8, active 60 trading days from `reporting_date`. Bernard & Thomas 1989 added to evidence base.

5. **[RISK]** Correlation-aware position sizing — `calculate_correlation_adjusted_size()`, Adjustment 3 in UC-07. Correlation > 0.70 → 25% reduction. Correlation > 0.85 → 50% reduction. 60-day lookback, minimum 30 overlapping days. Prevents hidden concentration risk when portfolio heat appears normal but correlated drawdown is 2–3× model prediction. New column: `correlation_adj_applied`. **Test 7H added to UC-10** — explicitly validates correlation adjustment adds OOS Calmar without reducing signal frequency > 10%. Gate: 7H-B Calmar ≥ 7H-A Calmar AND max drawdown ≤ 7H-A max drawdown.

6. **[RISK]** Explicit rebalancing logic — `monthly_rebalance()` function, UC-08B. 5-step specification: confirm RS exits, trim oversize positions, prohibit topping-up partial exits, fill Tier 1 slots only, flag (never auto-swap) score degradation vs challenger. Fixes missing operational definition — developer would have had no specification for what rebalancing actually executes. Pipeline step 30a added.

7. **[VALIDATION]** Adversarial walk-forward Fold 8 — UC-11. Train on non-bull years only (2015–2016 + 2018 + 2022). Test on 2019 bull recovery. Gate: OOS Sharpe ≥ 50% of Folds 1–4 average. Detects bull-market parameter overfit. `FOLD8_TRAIN_YEARS`, `FOLD8_TEST_YEAR`, `FOLD8_MIN_OOS_SHARPE_RATIO` added to settings.

---

## Changes v12 → v13

### 6 Evidence-Based Structural Fixes

1. **[EXIT]** RS exit persistence filter — replace hard `rs_rank < PHASE2_RS_FLOOR` single-day exit with a 4-consecutive-week persistence requirement. RS rank must remain below the floor for 4 full weeks before triggering exit. Single-week RS drops during consolidation are noise, not trend failure. Applied in Phase 2, Phase 3, and Phase 4. New counter: `rs_below_floor_weeks`. New setting: `RS_PERSIST_WEEKS = 4` (LOCKED).

2. **[MONSTER]** Monster override gain confirmation gate — monster override (Phase 4 rules regardless of actual gain) now requires BOTH `monster_score >= 80` AND `gain >= 40%`. At gain < 40%, monster score is tracked and displayed but does not change exit phase. Prevents Phase 4 loose exits being applied to unproven positions that scored high on entry profile but have not yet confirmed the move. New setting: `MONSTER_OVERRIDE_MIN_GAIN = 0.40` (LOCKED).

3. **[EXIT]** Time stop ATR compression suppression — time stop (`holding_days >= TIME_STOP_DAYS` with `gain < TIME_STOP_MAX_GAIN`) is suppressed if ATR is compressing. Specifically: if `atr_now < atr_entry * ATR_COMPRESS_SUPPRESS_RATIO`, the time stop condition does not fire. A flat price with shrinking ATR is a coiling base, not a dead trade. New function: `check_atr_compressing()`. New setting: `ATR_COMPRESS_SUPPRESS_RATIO = 0.70` (LOCKED).

4. **[RISK]** Regime-dependent portfolio heat — `MAX_PORTFOLIO_HEAT` is no longer a single flat value. Replaced with regime-tiered heat limits: Strong Bull 6%, Bull 5%, Weak 4%, Bear 2%, Full Bear 0%. Previous flat 4% was under-allocating during strong bull markets where momentum concentration is the source of alpha. New settings: `HEAT_STRONG_BULL`, `HEAT_BULL`, `HEAT_WEAK`, `HEAT_BEAR` (all LOCKED).

5. **[RISK]** Fast crash detector — new `check_fast_crash()` function. If market index declines more than 8% within any rolling 5-trading-day window, trigger immediate portfolio risk reduction (halve all position sizes, stop all new entries) regardless of regime score. The 6-signal regime engine is a structural filter with a 3-day stability rule — it is too slow for crash events. This is a separate, faster layer. New settings: `FAST_CRASH_PCT = 0.08` and `FAST_CRASH_DAYS = 5` (both LOCKED). Validated: March 2020 Nifty 50 dropped ~23% in 10 trading days — fast detector would have fired within the first 5.

6. **[MONSTER]** Monster score sector outperformance criterion — new criterion added to `calculate_monster_score()`: if stock outperforms its sector index by 2× or more over the prior 6 months, add +10 to monster score. This tests true sector leadership, not just absolute momentum. Maximum score remains 100 (cap enforced). New setting: `MONSTER_SECTOR_OUTPERFORM_MULT = 2.0` and `MONSTER_SECTOR_OUTPERFORM_BONUS = 10` (both LOCKED). Note: this is a scoring bonus, not a hard gate — some genuine monster stocks underperform their sector early before breaking out.

---

## Changes v11 → v12

### New Features (4 additions)

1. **[EXIT]** Volume direction during pullbacks — `vol_ratio < 0.75` on any day price is below 21DMA = hold override, reset `ma21_below_count` to 0. `vol_ratio >= 1.5` on any day price is below 21DMA = instant distribution confirmation, reduce 25% immediately without waiting for `MA21_CONFIRM_DAYS`. Applied in Phase 2 and Phase 3.

2. **[EXIT]** Higher highs / higher lows trend integrity check — `check_trend_integrity()` function added. If trend is INTACT: suppress 21DMA warning counter even on average volume. If trend is BROKEN: confirms exit signals regardless of volume. Applied in Phase 2 and Phase 3 as override layer on top of existing 21DMA logic.

3. **[EVIDENCE]** Bessembinder 2018 added to evidence base — top 4% of stocks drive all net stock market wealth creation. Reinforces Phase 4 loose exits and the Monster Stock Detection Layer. Justifies the asymmetric treatment of monster run candidates.

4. **[MONSTER]** Monster Stock Detection Layer — John Boik framework. `calculate_monster_score()` function added (0–100 score). If `MONSTER_SCORE >= 80`: override to Phase 4 exit rules regardless of actual gain phase. Full scoring criteria, schema additions, and watchlist panel added.

---

## Changes v10 → v11 (merged exit framework — simulation validated)

1. **[EXIT]** 21DMA warning + 3-day confirmation added to Phase 2/3 — reduces 25% on confirmed weakness, not immediate exit
2. **[EXIT]** Volatility-adjusted 50DMA: `price < (50DMA - 1.5×ATR)` replaces clean 50DMA break — avoids routine volatility exits
3. **[EXIT]** Climax run sell increased 25% to 50% — parabolic tops rarely continue, aggressive exit correct
4. **[EXIT]** Phase 4 primary: 10-week MA breach replaces 12% trail as primary Phase 4 exit
5. **[SIMULATION]** Force Motors: v11 = 8.8x vs old 7.2x — Phase 4 held through full ₹2,500 to ₹22,000 run
6. **[SIMULATION]** Himadri: partial exits crystallised at ₹300 and ₹450 — blended exit better than old MA200 wait
7. **[SIMULATION]** MA200 never fired as primary exit in either stock — confirmed as backstop only
8. **[SIMULATION]** 10/21 DMA would have exited Force Motors at 3–4x — Phase 2 loose trail proved correct

---

## Changes v9 → v10 (monster run exit redesign + evidence fixes)

1. **[EXIT]** Complete exit engine redesign — 4-phase gain-based framework replaces fixed trailing stops
2. **[EXIT]** Phase 1 (0–25%): fixed 8% stop only — prove-it phase, no trailing
3. **[EXIT]** Phase 2 (25–100%): loose 20% trail from 10-week high — let winners run, absorb corrections
4. **[EXIT]** Phase 3 (100–200%): 15% trail from 10-week high — working compounder, slightly tighter
5. **[EXIT]** Phase 4 (200%+): staged partial exits (25%+25%) + trail core 50% at 12% — monster run management
6. **[EXIT]** RS rank decay added as primary hold/sell signal — position exits when RS rank falls below top 30%
7. **[EXIT]** MA50 rising condition added to Phase 2/3/4 holds — structural trend confirmation
8. **[EXIT]** 10/21 DMA removed as exit trigger from all phases — too tight, destroys monster runs
9. **[RISK]** Default `RISK_PER_TRADE_PCT = 1.0%` (adaptive: set to 1.5/2.0 based on backtest win rate)
10. **[RISK]** `MAX_PORTFOLIO_HEAT` reduced 6% → 4%
11. **[EVIDENCE]** Lesmond, Schill & Zhou 2004 added to evidence base
12. **[EVIDENCE]** "Doubles Sharpe" corrected to "materially improves" (Barroso claim)
13. **[EVIDENCE]** OBV downgraded from "60-year evidence" to "practitioner-validated"
14. **[EVIDENCE]** Bonus score weights relabelled as initial estimates, not research-derived
15. **[EVIDENCE]** Crash indicator thresholds marked as FREE, calibrate in Test 3
16. **[EVIDENCE]** Promoter buying signal cites Lakonishok & Lee 2001 as proxy evidence
17. **[PARAMS]** `MOM_QUALITY_MIN = 0.55` moved from LOCKED to FREE (test in Test 1)
18. **[PARAMS]** `RS_RANK_MIN_PCT = 30` moved from LOCKED to FREE (test in Test 1)
19. **[PARAMS]** `VCP_MAX_DEPTH`, `VCP_MIN_CONTRACTIONS` moved from LOCKED to FREE (test in Test 6)
20. **[PARAMS]** `EARNINGS_SAFETY_DAYS = 10` moved from LOCKED to FREE (test in Test 6)
21. **[PARAMS]** `TRAIL_STOP_50PCT` removed (replaced by phase-based framework)
22. **[PARAMS]** `BACKTEST_START` extended to 2010-01-01 (12 years, 189 obs/param for 16 free params)
23. **[PARAMS]** Boundary rule added: if winning parameter at edge of range, extend and retest
24. **[VCP]** ATR compression check added to VCP quality scoring
25. **[EVIDENCE]** MA200 clarified as backstop only — primary exits are phase-based stops and RS decay

---

## 1. Non-Negotiable Principles

### ARCHITECTURE
- 3 fully separated engines: Alpha / Execution / Risk — never mix them
- Momentum is the ONLY stock selection signal
- Execution engine times entries only — does not select stocks
- Risk engine controls allocation only — no stock opinions

### DATA
- ALL calculations on `adj_close` — never raw close
- ALL fundamentals filtered by `reporting_date` — never `period_end_date`
- Survivorship bias: include ALL delisted stocks in backtest universe
- Delivery %: stored and displayed only — zero scoring, zero filtering

### UNIVERSE
- Main system: ₹1,000–₹30,000 crore market cap AND ₹15 crore daily traded value (audit-corrected March 2026 — see Flaw 3 in Known Discrepancies section)
- Both conditions mandatory — market cap alone is insufficient
- IPO exclusion: 200 trading days minimum history before any stock enters universe
- Large-cap graduation: auto exit signal when stock crosses ₹30,000cr ceiling
- Pre-profit watch list: loss-making + revenue >50% growth → watch list only

### HARD BLOCKS (8 — non-negotiable, any one = excluded)
1. EPS positive < 2 of last 4 reported quarters (→ watch list if revenue >50% growth)
2. Market cap outside ₹1,000–₹30,000cr OR avg daily traded value < ₹15cr (audit-corrected)
3. ASM/ESM surveillance list
4. SEBI price manipulation fine in last 24 months
5. Promoter pledge > 20% (operational) OR > 50% (infrastructure/project finance)
   - Infrastructure exception: D/E falling AND revenue >30% growth confirms project finance
6. 3+ business pivot / object clause changes in 5 years
7. IPO listed < 200 trading days ago
8. OCF negative in 3 of last 4 reported quarters

### PARAMETER DISCIPLINE
- Only 10 parameters freely optimised in backtest (see Section 9)
- All other parameters LOCKED at research-proven values
- Never re-run a test after seeing result to fine-tune — run once, lock result
- Track all N parameter trials — compute Deflated Sharpe Ratio after optimisation
- OOS 2023–2024 LOCKED before writing any backtest code

### VALIDATION SCOPE (important distinction)
- **40-stock manual test (Section 8) = LOGIC VALIDATION only.** Proves each rule fires correctly on named stocks. Not performance evidence. Not statistically sufficient for performance claims.
- **Full-universe backtest (Tests 1–16) = PERFORMANCE EVIDENCE.** Covers all NSE stocks in ₹1,000–₹30,000cr band 2015–2022 (~800–1,200 unique stocks including delisted). This is the only evidence base for return and Sharpe claims.
- Never confuse the two in any communication to clients or investors.

### OPERATIONAL RULES
- Earnings due within 10 days → auto-downgrade signal to Tier 3
- Next-day open > pivot + 3% → signal expires, do not enter
- Circuit-locked stocks → exclude from VCP detection
- Nothing goes live without passing all 20 gates in UC-13

### ADV DECLINE RULE (Fix P2 — prevents hidden survivorship bias)
- Liquidity filter (₹15cr ADV — audit-corrected default) applies at ENTRY only — never post-entry
- If a stock's ADV drops below MIN_DAILY_TRADED_VALUE_CR AFTER a position is entered:
  - Position stays open, subject to normal exit rules only
  - Do NOT auto-exit on ADV crossing below threshold
  - Exit only via: stop loss / MA200 breach / regime / trailing stop
- Rationale: auto-exiting on ADV decline silently removes losing positions from backtest P&L creating survivorship bias even with delisted stocks included
- Implementation: backtest position table stores `entry_adv` separately. Liquidity gate checked only at signal generation date, never post-entry.

---

## 2. System Architecture

```
NSE UNIVERSE (~4,000+ stocks)
 |
 | UNIVERSE PRE-FILTER:
 | - Market cap ₹1,000–₹30,000cr AND ADV >= ₹15cr (audit-corrected)
 | - IPO age >= 200 trading days
 | - Active, not delisted
 | ~300–500 stocks pass
 |
 v
┌─────────────────────────────────────────────────────┐
│ 8 HARD BLOCKS (junk + fraud removal)                │
│ EPS junk | ASM/ESM | SEBI fine | Pledge threshold   │
│ Business pivot | IPO age | OCF quality | Mkt cap    │
│ → Pre-profit watch list for revenue >50% growth     │
└─────────────────────────────────────────────────────┘
 |
 | ~200–300 eligible stocks
 v
┌─────────────────────────────────────────────────────┐
│ ENGINE A — ALPHA ENGINE                             │
│ Sector ranking — daily (UC-04 Step 0 — NEW v14)     │
│ Multi-timeframe momentum: 12-1m / 6m / 3m          │
│ Volatility scaling (Barroso & Santa-Clara 2015)     │
│ RS rank filter: top 30% vs Nifty 50                 │
│ Momentum quality >= 0.55 (smooth uptrend filter)    │
│ Fundamental bonus scores (NOT hard filters)         │
│ PEAD earnings surprise bonus (NEW v14)              │
│ Penalty signals (reduce score, never eliminate)     │
│ Sector bonus / penalty                              │
│ Monster score calculation (v12)                     │
└─────────────────────────────────────────────────────┘
 |
 | ELIGIBLE UNIVERSE: top 15–20%, ~60–80 stocks
 v
┌─────────────────────────────────────────────────────┐
│ ENGINE B — EXECUTION ENGINE                         │
│ 8-condition Minervini trend template                │
│ VCP / Tight base / Breakout detection               │
│ OBV slope check during base (from base_start only)  │
│ False breakout filter (2-day confirmation)          │
│ Entry rules: vol 1.5x, circuit check, close pos     │
│ Max entry: open > pivot+3% → signal expires         │
│ Earnings safety: results <10 days → Tier 3          │
└─────────────────────────────────────────────────────┘
 |
 | SIGNALS: Tier 1 / Tier 2 / Tier 3
 v
┌─────────────────────────────────────────────────────┐
│ ENGINE C — RISK ENGINE                              │
│ 6-signal regime score + crash indicator             │
│ Fast crash detector — 8% in 5 days (v13)            │
│ 5-layer exit cascade (UC-03B)                       │
│ 4-phase bull entry protocol (UC-03C)                │
│ 2% risk rule position sizing                        │
│ Beta >2.5: 40% size reduction                       │
│ Thin float (private >75%): 40% reduction            │
│ Correlation-aware sizing (NEW v14)                  │
│ Regime-dependent portfolio heat (v13)               │
│ Sector concentration cap (max 30%)                  │
│ Drawdown circuit breaker                            │
│ Volume pullback direction filter (v12)              │
│ Trend integrity check (v12)                         │
│ Monster stock override — gain-gated (v13)           │
│ RS persistence filter — 4-week (v13)                │
│ Time stop ATR suppression (v13)                     │
│ Monthly rebalance logic (NEW v14)                   │
└─────────────────────────────────────────────────────┘
 |
 v
 FINAL WATCHLIST (max 20 stocks + monster candidates panel)
 |
 v
 BACKTEST 2015–2022 → WALK-FORWARD → OOS 2023–2024
 |
 v
 PAPER TRADE 6 months → GO LIVE 10% capital
```

---

## 3. Data Sources

### 3.0 Stock-to-Sector Mapping — NSE Classification (LOCKED)

**Decision (v14):** All sector classification uses NSE's official sector/industry master. This is the correct and only source for sector data in MomentumEdge. Screener.in, BSE, and any third-party classifications are explicitly rejected for this field.

**Rationale:** NSE sector data is the same source as all price data. Zero mapping inconsistency. 100% universe coverage by definition. Updates automatically on NSE reclassification. No third-party dependency for a structural field that affects sector rankings, sector bonus/penalty, sector concentration cap, and monster score sector rank.

```
URL: nseindia.com/api/equity-master
Fields: symbol, companyName, industry, sector
Update: Quarterly or on NSE reclassification event
Storage: stocks table — sector VARCHAR(50), industry VARCHAR(50)
Level: Use SECTOR (22 broad groups) not INDUSTRY (80 sub-groups)

Reason for sector not industry:
  At sub-industry level, many groups have only 3-5 stocks.
  calculate_sector_rankings() uses median of member stocks.
  With < 5 members, median is statistically unreliable.
  22-sector level gives 10-60 stocks per sector — robust median.

NSE 22 broad sectors (reference):
  Automobile | Banks | Capital Goods | Chemicals | Construction
  Consumer Durables | Consumer Services | FMCG | Financial Services
  Healthcare | IT | Media | Metals & Mining | Oil Gas & Consumable Fuels
  Pharma | Power | PSU Banks | Realty | Services | Telecom
  Textiles | Diversified
```

**Implementation rule:** On UC-01 first run, download equity master and populate `sector` and `industry` fields in `stocks` table. Check weekly for reclassifications — NSE announces these in corporate actions feed. Log any reclassification with old and new sector for audit trail.

---

### 3.1 Price Data — NSE Archive (Primary, Free)

```
URL pattern:
archive.nseindia.com/content/historical/EQUITIES/{YEAR}/{MON}/cm{DD}{MON}{YYYY}bhav.csv.zip
Fields: SYMBOL, SERIES, OPEN, HIGH, LOW, CLOSE, TOTTRDQTY, TOTTRDVAL, ISIN
Filter: SERIES == 'EQ' only
Coverage: Free, official, 1994–present
Store: raw close AND adj_close separately in price_data table
Note: Include ALL stocks including later-delisted — survivorship bias prevention
Exchange column: store exchange = 'NSE' on all rows — required for future BSE expansion
```

### 3.2 Delivery Data — NSE Archive (Store Only, Never Score)

```
URL: archives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv
Fields: SYMBOL, QUANTITY_TRADED, DELIVERABLE_QTY, PERCENT_DELI_QTY_TO_TRADED_QTY
Store: delivery_qty, delivery_pct in price_data table
Score: ZERO — never used in any scoring or filtering
Display: Show as context in dashboard only
Reason: No academic evidence. Operator-contaminated in mid-caps.
        Replaced by OBV (Granville 1963, 60yr evidence).
```

### 3.3 Corporate Actions — NSE API (Critical for adj_close)

```
URL: nseindia.com/api/corporates-corporateActions
     ?index=equities&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY
Fields: symbol, exDate, purpose (split/bonus/rights/dividend), ratio
Use: Calculate cumulative adj_factor → populate adj_close backwards
Rule: EVERY price calculation uses adj_close — never raw close
Verify: Manually check 10 known split/bonus events before backtest
Cross-check: BSE corporate actions announcement (see Section 3.7) for earlier confirmation
```

### 3.4 Fundamentals — Screener.in Premium API

```
Cost: ~₹5,000/year
Critical fields:
  reporting_date         — when results ANNOUNCED (ALWAYS filter by this)
  period_end_date        — quarter end date (stored but NEVER used as filter date)
  eps                    — earnings per share
  eps_growth_yoy         — YoY growth vs same quarter last year (used by SUE proxy bonus)
  revenue_cr             — quarterly revenue
  operating_profit_cr    — operating profit
  opm_pct                — operating profit margin %
  net_profit_cr          — net profit after tax
  other_income_cr        — non-operating income (for other income quality check)
  ocf_cr                 — operating cash flow (for OCF quality check)
  debt_to_equity         — D/E ratio
  trade_receivables_days — debtors days (for debtors penalty)
  promoter_pledge_pct    — promoter shares pledged % (for pledge hard block)
  expected_result_date   — upcoming results date (for earnings safety rule)
  is_financial           — skip D/E scoring for banks/NBFCs
```

**Note on analyst estimates (v14 decision):** Screener.in Premium does NOT provide analyst consensus EPS estimates (`analyst_estimate_eps`). This field has been removed from the schema. The SUE proxy bonus (`calculate_sue_proxy_bonus()`) uses `eps_growth_yoy` which Screener.in does provide, giving 100% universe coverage with zero additional data source. If a future data source (e.g. Trendlyne) provides analyst consensus estimates at adequate coverage (>50% of universe), upgrade Bonus 9 to true analyst-vs-actual comparison at that point.

### 3.5 Institutional Flow Data — NSE Daily

**Source 1 — FII/DII aggregate (daily):**
```
URL: nseindia.com/api/fiidiiTradeReact
Fields: date, fii_net_buy_cr, dii_net_buy_cr
Store in fii_dii_data table with sector breakdown
```

**Source 2 — Shareholding pattern (quarterly):**
```
URL: Screener.in API or BSE shareholding XML
Fields: promoter_pct, fii_pct, dii_pct, public_pct
Update quarterly when companies file with exchanges
```

**Source 3 — NSE FII breach/caution list (daily):**
```
URL: nseindia.com/market-data/securities-available-for-trading
Fields: symbol, fii_limit_pct, current_fii_holding_pct, is_breached, is_cautioned
Use: If stock on breach list → FII buying legally blocked → skip FII signal
```

**Source 4 — Bulk/block deals (daily):**
```
URL: nseindia.com/market-data/block-deal
Fields: date, symbol, client_name, deal_type, quantity, price, value_cr
Use: For high-promoter or FII-capped stocks — institutional bulk buy = strongest signal
```

### 3.6 Delisted Stocks — Required for Backtest

NSE bhav copy contains data for delisted stocks up to last trading date. MUST include all stocks that were in ₹1,000–₹30,000cr band 2015–2024 even if later delisted, suspended, or merged. Ignoring delisted stocks overstates backtest returns by 30–50%. This is survivorship bias — the single most common backtest flaw.

### 3.7 BSE Data — Cross-Validation Now, Full Expansion Later

**Current status (v14):** MomentumEdge trades NSE-listed equities only. BSE data is used for cross-validation and data quality checks — not for signal generation or universe construction.

**Future status:** BSE will be added as a full parallel data stream in a future version. The schema is designed now to support this with zero rework — see exchange column in `price_data` table.

---

**BSE vs NSE universe overlap:**

At ₹1,000–₹30,000cr market cap, BSE and NSE overlap is approximately 95%+. The 5% difference is concentrated in the ₹1,000–₹2,000cr band where some stocks chose BSE as primary listing. The ISIN field is the definitive cross-reference — same ISIN = same company regardless of exchange.

```
NSE-only listings (mid-cap level): rare, mostly newer listings
BSE-only listings (mid-cap level): ~5% of universe, mostly ₹1,000-2,000cr band
Dual-listed (both exchanges):      ~95% of ₹1,000cr+ universe
```

---

**BSE data for cross-validation (USE NOW):**

```
BSE bhav copy (daily price validation):
URL: bseindia.com/download/BhavCopy/Equity/EQ{DDMMYYYY}_CSV.ZIP
Fields: CODE, NAME, OPEN, HIGH, LOW, CLOSE, TOTTRDQTY, TOTTRDVAL, ISIN
Join key: ISIN (links BSE CODE to NSE SYMBOL)
Use: Compare NSE adj_close vs BSE price on same day
     Flag if divergence > 0.5% on same ISIN — data quality alert
     Do NOT use for scoring — NSE is primary

BSE corporate actions (earlier announcements):
URL: bseindia.com/corporates/ann.html
Use: BSE sometimes announces corporate actions 1-2 days before NSE API updates
     Cross-check BSE corporate actions against NSE daily
     If BSE shows a new action not yet in NSE feed → flag for manual review
     Never apply adj_factor from BSE — only use as early-warning check

BSE shareholding (XML, quarterly):
URL: bseindia.com/corporates/shp/shareholdingPattern.aspx
Fields: promoter_pct, fii_pct, dii_pct, public_pct, promoter_pledge_pct
Use: Cross-validate NSE/Screener shareholding data
     If BSE and Screener promoter_pledge_pct diverge > 2% → use higher (conservative)
     BSE filings sometimes updated faster than Screener.in
```

**Data quality cross-check rule (add to UC-01 Step 7):**
```python
def cross_check_bse_nse(nse_price, bse_price, isin, date, tolerance=0.005):
    """
    Compare NSE adj_close vs BSE close on same ISIN.
    Divergence > 0.5% on a non-ex-date = data quality flag.
    Does not block pipeline — logs alert only.
    """
    if abs((nse_price - bse_price) / bse_price) > tolerance:
        log_data_quality_alert(
            isin    = isin,
            date    = date,
            nse_px  = nse_price,
            bse_px  = bse_price,
            reason  = 'nse_bse_price_divergence'
        )
```

---

**BSE full expansion — future version schema design (LOCKED NOW, BUILD LATER):**

The `price_data` table already has `exchange VARCHAR(5)` column (add this — see schema Section 6). When BSE is added as a full data stream, the only schema change required is populating this column. All existing queries filter by symbol — adding `AND exchange = 'NSE'` to existing queries is the only code change needed.

```sql
-- Future BSE expansion — schema already supports this
-- price_data PRIMARY KEY changes from (symbol, date) to (symbol, date, exchange)
-- All NSE rows: exchange = 'NSE'
-- All BSE rows: exchange = 'BSE'
-- ISIN in stocks table is the cross-reference key

-- Future BSE-only stock additions:
-- When a stock trades on BSE only (no NSE listing):
--   symbol = BSE scrip code (numeric, e.g. '532540')
--   exchange = 'BSE'
--   isin = standard ISIN (links to fundamentals)
--   All fundamental data joined on ISIN, not symbol

-- Dual-listed stocks:
--   Two rows in price_data per day (one NSE, one BSE)
--   Signals generated from NSE price (primary)
--   BSE price stored for cross-validation only
--   Never generate two signals for the same ISIN
```

**BSE expansion trigger:** Add BSE as full signal source when either (a) you identify material alpha in BSE-only mid-cap listings not available on NSE, or (b) you expand universe below ₹1,000cr where BSE-only listings become more common. Neither condition applies at current scope.

---

### UC-01: Daily Data Ingestion

**Trigger:** 4:15 PM IST every NSE trading day  
**Postcondition:** Database updated with today's price, delivery, FII data.

**Flow:**
1. Check NSE holiday calendar — if holiday, log skip and exit
2. Download bhav copy → parse EQ series stocks only
3. Download delivery bhav copy → `delivery_qty`, `delivery_pct`
4. Download FII/DII net activity → `fii_dii_data` table
5. Download bulk/block deals → `bulk_deals` table
6. Check corporate actions → apply `adj_factor` if new action found
6a. **Download BSE bhav copy → run `cross_check_bse_nse()` on all dual-listed stocks. Log divergence > 0.5% as data quality alert. Do not block pipeline. (Section 3.7)**
6b. **Check BSE corporate actions feed → if new action found not yet in NSE feed → flag for manual review. Never apply adj_factor from BSE directly.**
7. Run validation gate:
   - 2% stocks missing → halt and alert admin
   - Single-day move > 25% without corporate action → flag for review
   - 3+ consecutive zero volume days on any stock → exclude from universe
   - Bhav copy date ≠ today → halt
8. Write raw close AND `adj_close` to `price_data` with `exchange = 'NSE'`
9. Check promoter pledge updates (quarterly) → update `stocks` table. Cross-validate against BSE shareholding XML if available.
10. Log success → trigger UC-02

**Backtest verification:**
- Verify `adj_close` on 10 known split/bonus events manually before any backtest
- Verify delivery data stored correctly but NOT used in any scoring

---

### UC-02: Indicator Calculation

**Postcondition:** All indicators calculated on `adj_close` for all universe stocks.

```python
def calculate_indicators(symbol, as_of_date, price_df):
    p = price_df[price_df['symbol']==symbol]['adj_close'].sort_index()
    v = price_df[price_df['symbol']==symbol]['volume'].sort_index()

    # ── Moving averages — all on adj_close ──────────────────────────
    ma50  = p.rolling(50).mean().iloc[-1]
    ma150 = p.rolling(150).mean().iloc[-1]
    ma200 = p.rolling(200).mean().iloc[-1]
    ma200_slope = ma200 - p.rolling(200).mean().iloc[-21]

    # ── Momentum returns — all on adj_close ─────────────────────────
    mom_3m   = (p.iloc[-1] / p.iloc[-63])  - 1
    mom_6m   = (p.iloc[-1] / p.iloc[-126]) - 1
    mom_12_1 = (p.iloc[-21] / p.iloc[-252]) - 1   # skip most recent month

    # ── Volatility scaling (Barroso & Santa-Clara 2015) ─────────────
    daily_ret    = p.pct_change()
    mom_vol_20d  = daily_ret.rolling(20).std().iloc[-1]
    vol_annualised = mom_vol_20d * (252**0.5)
    vol_scalar   = min(0.20 / vol_annualised, 2.0) if vol_annualised > 0 else 1.0

    # ── Momentum quality (smooth uptrend filter) ─────────────────────
    weekly       = p.resample('W').last().pct_change()
    mom_quality  = (weekly.tail(26) > 0).sum() / 26

    # ── OBV — full history value only (slope calculated per-base in UC-06) ──
    sign = p.diff().apply(lambda x: 1 if x>0 else (-1 if x<0 else 0))
    obv  = (sign * v).cumsum().iloc[-1]
    # IMPORTANT: OBV slope during VCP base calculated in UC-06 from base_start only
    # Do NOT use full-history OBV slope — pre-base events distort it

    # ── A/D ratio (Minervini accumulation/distribution days) ─────────
    last20   = price_df[price_df['symbol']==symbol].tail(20)
    up_vol   = last20[last20['adj_close']>last20['adj_close'].shift(1)]['volume'].sum()
    dn_vol   = last20[last20['adj_close']<last20['adj_close'].shift(1)]['volume'].sum()
    adl_ratio = up_vol/(up_vol+dn_vol) if (up_vol+dn_vol)>0 else 0.5

    # ── Volume ratios ────────────────────────────────────────────────
    vol_ratio_20 = v.iloc[-1] / v.rolling(20).mean().iloc[-1]
    vol_ratio_50 = v.iloc[-1] / v.rolling(50).mean().iloc[-1]

    # ── 52-week metrics ──────────────────────────────────────────────
    week52_high  = p.tail(252).max()
    week52_low   = p.tail(252).min()
    pct_from_high = (p.iloc[-1] / week52_high) - 1

    # ── Delivery trend (stored, displayed, NEVER scored) ────────────
    delivery      = price_df[price_df['symbol']==symbol]['delivery_pct']
    delivery_trend = delivery.tail(10).mean() - delivery.tail(20).head(10).mean()

    return {
        'ma50': ma50, 'ma150': ma150, 'ma200': ma200,
        'ma200_slope': ma200_slope,
        'mom_3m': mom_3m, 'mom_6m': mom_6m, 'mom_12_1': mom_12_1,
        'vol_scalar': vol_scalar, 'mom_vol_20d': mom_vol_20d,
        'mom_quality': mom_quality,
        'obv': obv,          # full value only — slope per-base in UC-06
        'adl_ratio': adl_ratio,
        'vol_ratio_20': vol_ratio_20, 'vol_ratio_50': vol_ratio_50,
        'week52_high': week52_high, 'week52_low': week52_low,
        'pct_from_high': pct_from_high,
        'delivery_trend': delivery_trend  # display only, never scored
    }
```

---

### UC-03: Market Regime Detection (Engine C — Layer 1)

**Postcondition:** Regime score, crash warning, allocation parameters stored.

**6 Regime Signals**

| Signal | Rule | Score |
|---|---|---|
| S1 | Nifty close > MA200 | 0 or 1 |
| S2 | MA200 today > MA200 20d ago | 0 or 1 |
| S3 | Nifty500 stocks above 50MA: >60%=1, 40–60%=0.5, <40%=0 | 0–1 |
| S4 | NH/NL ratio on Nifty500: >2x=1, equal=0.5, lows>highs=0 | 0–1 |
| S5 | Nifty distance from 200MA: 0–15%=1, 15–25%=0.5, >25%=0 | 0–1 |
| S6 | Nifty 12-1 month return positive | 0 or 1 |

**Momentum Crash Indicator (Dierkes & Krupski 2022)**

```python
nifty_2yr_return = (nifty_today / nifty_504d_ago) - 1
nifty_1m_return  = (nifty_today / nifty_21d_ago) - 1
crash_warning    = (nifty_2yr_return < -0.20) and (nifty_1m_return > 0.10)
# Both conditions = momentum crash risk (validated: April 2020, March 2009)
# If crash_warning = True: force regime to Full Bear regardless of score
```

**Regime Allocation Table**

| Score | Regime | Max Equity | Max Positions | Risk/Trade |
|---|---|---|---|---|
| 5.0–6.0 | Strong Bull | 100% | 15 | 2.0% |
| 4.0–5.0 | Bull | 80% | 12 | 1.5% |
| 2.5–4.0 | Weak | 50% | 8 | 1.0% |
| 1.0–2.5 | Bear | 25% | 4 (existing only) | 0.5% |
| 0–1.0 or crash | Full Bear | 0% | 0 | Exit all |

**Stability rule:** Regime changes only after 3 consecutive days at new level (prevents whipsawing).

**Backtest validation events (must verify in Test 3):**
- March 2020 → Full Bear within 5 trading days
- April 2020 → crash indicator fires (2yr down + 1m rally)
- July 2020 → Bull transition (the single most important signal in 5 years)
- Oct–Nov 2021 → Weak/Bear as midcap breadth deteriorates
- 2022 rate hike period → Bear correctly during FII selloff

---

### UC-03D: Fast Crash Detector (NEW v13)

**Purpose:** The 6-signal regime engine has a 3-day stability rule and is designed as a structural filter. It is too slow to protect capital during sudden crash events. The fast crash detector is a separate, independent layer that fires immediately on violent market moves — before the regime engine has time to transition.

**Rationale:** March 2020 — Nifty 50 dropped ~23% in 10 trading days. The regime engine would have transitioned to Full Bear by day 5–7. The fast crash detector fires within the first 5 days, materially reducing drawdown. The 2020 crash is the primary validation event. The 2008 crisis and multiple flash corrections also support this design.

**Interaction with regime engine:** Fast crash detector and regime engine are independent. Either one alone can trigger risk reduction. Fast crash is faster but temporary — it resets when the 5-day loss condition is no longer met. Regime stays until 3 consecutive days at new level. Both must be checked daily.

```python
def check_fast_crash(nifty_df, as_of_date):
    """
    Fast crash detector — NEW v13.
    Fires if market index declines more than 8% within any rolling
    5-trading-day window. Independent of regime engine.

    Response:
      - Halve all open position sizes immediately (sell 50% of each)
      - Stop all new entries until fast_crash_active resets
      - Log fast_crash_fired = True in regime_history

    Reset condition:
      - fast_crash_active resets when NO rolling 5-day window
        in the last 10 trading days shows a decline > 8%

    Validated: March 2020 — Nifty 50 lost ~12% in first 5 trading days
               of the crash (Feb 28 – Mar 6 2020). Fast detector fires.
               Regime engine needed until Mar 12–16 to fully transition.
    """
    prices = nifty_df['close'].tail(FAST_CRASH_DAYS + 1)

    if len(prices) < FAST_CRASH_DAYS + 1:
        return False   # insufficient history

    for i in range(len(prices) - FAST_CRASH_DAYS):
        window_start = prices.iloc[i]
        window_end   = prices.iloc[i + FAST_CRASH_DAYS]
        if window_start > 0:
            window_return = (window_end / window_start) - 1
            if window_return <= -FAST_CRASH_PCT:
                return True  # fast crash detected

    return False


def apply_fast_crash_response(open_positions, portfolio_value):
    """
    Called when check_fast_crash() returns True.
    Sell 50% of every open position at next available open.
    Block all new entries until fast_crash_active = False.
    """
    actions = []
    for position in open_positions:
        if position['is_active']:
            sell_shares = position['shares'] // 2
            if sell_shares > 0:
                actions.append({
                    'symbol':      position['symbol'],
                    'action':      'REDUCE_50PCT',
                    'sell_shares': sell_shares,
                    'reason':      'fast_crash_detector'
                })
    return actions
```

**Fast crash detection in daily pipeline:** Checked at Step 11 immediately after regime calculation. If `check_fast_crash()` returns True and `fast_crash_active` was previously False: execute `apply_fast_crash_response()` at next open. Store `fast_crash_active = True` in `regime_history`. Log all affected positions in `performance_log` with `exit_reason = 'fast_crash_partial'`.

**Interaction with Phase 4 monster override (v16 — explicit rule):** Fast crash response halves ALL open positions including Phase 4 monster cores. Risk management always takes priority over alpha management during a crash event. Monster override resumes automatically after `fast_crash_active` resets to False — the 10-week MA floor and Phase 4 exit rules re-engage on the reduced position size. The monster override flag (`monster_override_active`) is NOT cleared by fast crash — it remains True so Phase 4 rules resume immediately on reset. This means: crash happens → halve monster position → crash resolves → Phase 4 rules continue on remaining half. No re-entry or re-activation required.

---

**Purpose:** Exit positions 4–8 weeks before MA200 breach. By the time MA200 breaks, portfolio is already 70–80% cash. Validated against October 2021 NSE market top. All 5 layers checked daily for every open position AND at portfolio level.

**Exit Layer E1: Climax Run Detection (Earliest Signal)**

```python
def check_climax_run(position, price_df):
    """
    Fires weeks before any market-level signal.
    Stocks making parabolic moves after large gains = distribution phase.
    """
    gain_from_entry = (current_price / position['entry_price']) - 1
    if gain_from_entry < 0.80:
        return False  # need 80%+ gain first

    # Check if stock advanced >30% in any rolling 15-day window
    recent_30d = price_df.tail(30)['adj_close']
    for i in range(len(recent_30d) - 15):
        window_gain = (recent_30d.iloc[i+15] / recent_30d.iloc[i]) - 1
        if window_gain > 0.30:
            return True  # climax run detected
    return False

# Response: sell 25% immediately, sell 25% at next new high,
# sell remainder on any close below 10-day MA
```

**Exit Layer E2: Distribution Day Counter (Index Level)**

```python
def update_distribution_count(nifty_df, rolling_window=25):
    """
    Distribution day = index closes down >0.2% on higher volume than prior day.
    Institutional selling signature.
    """
    count = 0
    recent = nifty_df.tail(rolling_window)
    for i in range(1, len(recent)):
        price_down = recent['close'].iloc[i] < recent['close'].iloc[i-1] * 0.998
        vol_higher = recent['volume'].iloc[i] > recent['volume'].iloc[i-1]
        if price_down and vol_higher:
            count += 1
    return count

# Response:
# count 3–4: no new entries, tighten trailing stops to 10-day MA
# count >= 5: reduce all positions 25%, stop all new entries
# count >= 6: reduce all positions to 50% of current size
```

**Exit Layer E3: A/D Line Divergence (Most Leading Signal, 4–12 weeks)**

```python
def check_ad_divergence(nifty_df, ad_line_df, lookback_weeks=3):
    """
    Index makes new high but A/D line makes lower high = breadth deteriorating.
    Documented leading indicator of every major market top since 1930s.
    """
    recent = nifty_df.tail(lookback_weeks * 5)
    nifty_new_high = recent['close'].iloc[-1] >= recent['close'].max() * 0.99
    ad_lower_high  = ad_line_df.tail(lookback_weeks * 5).iloc[-1] < \
                     ad_line_df.tail(lookback_weeks * 5).max() * 0.98
    return nifty_new_high and ad_lower_high

# Response: reduce all positions 25% immediately
```

**Exit Layer E4: New Highs Count Collapse**

```python
def get_new_highs_count(price_df, universe_symbols, as_of_date):
    """
    Count Nifty500 stocks making new 52-week highs on days index is near ATH.
    """
    count = 0
    for symbol in universe_symbols:
        p = price_df[price_df['symbol']==symbol]['adj_close']
        if p.iloc[-1] >= p.tail(252).max() * 0.99:
            count += 1
    return count

# Response:
# count < 50: tighten all individual stops to 15% trailing from recent high
# count < 20: reduce all positions to 50% of current size
```

**Exit Layer E5: Tiered Trailing Stop Cascade**

```python
def calculate_trailing_stop(position, current_price):
    gain = (current_price / position['entry_price']) - 1
    recent_10d_high = get_10d_high(position['symbol'])

    if gain < 0.20:
        return position['entry_price'] * (1 - 0.08)     # -8% from entry
    elif gain < 0.50:
        return position['entry_price']                   # breakeven stop
    elif gain < 1.00:
        return recent_10d_high * (1 - 0.15)             # 15% trail
    elif gain < 2.00:
        return recent_10d_high * (1 - 0.10)             # 10% trail
    else:
        # 200%+ gain: tightest trail + 10-day MA as primary
        ma10 = get_ma10(position['symbol'])
        return max(recent_10d_high * (1 - 0.08), ma10)  # 8% trail or MA10

# Also: MA200 breach on weekly close = mandatory full exit within 3 trading days
# No exceptions regardless of fundamentals
```

---

### UC-03C: Bull Market Entry Protocol

**Purpose:** Structured 4-phase re-entry after Bear regime. Prevents buying into failed bear market rallies. Deploy 25% capital per phase — never full deployment on one signal.

**PHASE B1 — CAPITULATION DETECTION (Watch mode, no capital)**
```
Trigger: Panic volume spike >2x 20-day average on Nifty500
         AND A/D line makes higher low while price makes new low
Action:  WATCH mode only. Zero capital deployed.
         Alert: "Market may be forming a bottom. Watch for breadth thrust."
Validated: March 2020 — highest single-day NSE volume in history.
           A/D making higher low vs Dec 2019.
```

**PHASE B2 — BREADTH THRUST (Deploy 25%)**
```
Trigger: Single day where 90%+ of Nifty500 advancing stocks'
         combined volume exceeds 90% of total Nifty500 volume
Action:  Deploy 25% of intended capital
         Start scanning for first Stage 2 setups
Why stronger than O'Neil follow-through day:
         FTD false positive rate = ~50%. Breadth thrust false positive rate = ~0%.
         Structurally impossible to fake — requires entire market to move together.
         Has never occurred mid-bear-market in 75 years of US data.
```

**PHASE B3 — A/D LINE CONFIRMATION (Deploy additional 25%)**
```
Trigger: A/D line for Nifty500 makes higher high than its level
         at the capitulation bottom (confirms broad recovery,
         not narrow large-cap bounce)
Action:  Deploy additional 25%
         Active VCP scanning begins for all eligible stocks
Validated: July 2020 — Nifty500 A/D line making strong new highs
           alongside index. Confirmed genuine bull, not rally.
```

**PHASE B4 — NEW HIGHS EXPAND (Full deployment)**
```
Trigger: Nifty500 new 52-week highs > 100 stocks per week
         for 2+ consecutive weeks
Action:  Full deployment per current regime allocation
         All Tier 1 signals executable
Validated: July 2020 — midcap and smallcap stocks breaking out
           simultaneously. Entry window for Himadri, GPIL, Tanla,
           Deepak Nitrite, Mazagon Dock.
```

---

### UC-04: Momentum Ranking and Eligible Universe (Engine A)

**Postcondition:** Eligible Universe of 60–80 stocks with volatility-scaled composite scores.

#### Step 0: Sector Ranking Calculation (NEW v14 — runs before composite scoring)

**Critical implementation note:** In v13 and earlier, sector rank was passed as a parameter to `build_composite_score()` but was never defined or computed anywhere in the document. This was a missing implementation definition that would have caused a developer wall. Step 0 defines the exact calculation.

```python
def calculate_sector_rankings(price_df, sector_map, as_of_date,
                               lookback_days=63):
    """
    Rank all NSE sectors by equal-weighted median 3-month momentum
    of all eligible member stocks.

    Runs ONCE daily before any composite scoring — output feeds
    sector_bonus and sector_penalty in build_composite_score().

    Lookback: 63 trading days = 3 months = same as mom_3m.
    Aggregation: median (not mean) — reduces impact of outlier stocks
                 in thin sectors.
    Update frequency: daily, stored in sector_rankings table.

    Returns: dict {sector_name: rank} where rank 1 = strongest sector.

    Evidence: Sector momentum has documented persistence of 3–12 months
    (Moskowitz & Grinblatt 1999 — sector momentum explains most individual
    stock momentum). A stock in the #1 sector with strong individual
    momentum materially outperforms an identical stock in the #10 sector.
    """
    sector_scores = {}

    for sector, symbols in sector_map.items():
        returns = []
        for sym in symbols:
            p = price_df[price_df['symbol'] == sym]['adj_close']
            if len(p) >= lookback_days + 1:
                ret = (p.iloc[-1] / p.iloc[-lookback_days]) - 1
                returns.append(ret)
        if returns:
            sector_scores[sector] = float(np.median(returns))
        else:
            sector_scores[sector] = 0.0   # no data — neutral

    # Rank 1 = strongest, ascending integer ranks
    ranked = sorted(sector_scores, key=sector_scores.get, reverse=True)
    sector_ranks = {sector: rank + 1 for rank, sector in enumerate(ranked)}

    # Store in sector_rankings table
    total_sectors = len(ranked)
    for sector, rank in sector_ranks.items():
        upsert_sector_ranking(
            date        = as_of_date,
            sector      = sector,
            rank        = rank,
            total       = total_sectors,
            score       = sector_scores[sector],
            is_top3     = rank <= 3,
            is_bottom3  = rank >= total_sectors - 2
        )

    return sector_ranks, total_sectors


def get_sector_rank_for_stock(symbol, sector_ranks):
    """
    Returns (sector_rank, total_sectors) for a given stock.
    Used in build_composite_score() for sector bonus/penalty calculation.
    Replaces the previously undefined sector_rank parameter.
    """
    sector = get_stock_sector(symbol)
    rank   = sector_ranks.get(sector, len(sector_ranks) // 2)  # default mid
    total  = len(sector_ranks)
    return rank, total
```

**Sector bonus/penalty application (unchanged from v12/v13, now properly sourced):**
```python
# In build_composite_score() — sector_rank now comes from Step 0 output
sector_rank, total_sectors = get_sector_rank_for_stock(symbol, sector_ranks)
if sector_rank <= 3:
    sector_bonus = BONUS_SECTOR_TOP3     # +10
elif sector_rank >= total_sectors - 2:
    sector_bonus = PENALTY_SECTOR_BOT3  # -5
else:
    sector_bonus = 0
```

**Reference: Moskowitz & Grinblatt 1999** — "Do Industries Explain Momentum?" Journal of Finance. Sector momentum accounts for a large portion of individual stock momentum. Adding explicit sector rank calculation ensures the bonus/penalty scoring is grounded in a computed daily signal rather than an undefined external input.

#### Step 0B: Earnings Turnaround Watch Scan (NEW v16 — runs after Step 0, before Step 1)

**Purpose:** Give Mohit advance warning 1–3 quarters before the EPS hard block clears on genuine business turnarounds. This is a monitoring and alerting function only — it does NOT generate buy signals, does NOT bypass hard blocks, and does NOT change any entry logic.

**Origin:** GE Vernova T&D India 2020–2024 simulation. System entered at ₹350–₹380. Stock was at ₹220–₹240 in June 2023 — 3 months before Q1 FY24 results confirmed EPS block clearance. Option C adds Turnaround Watch dashboard alert at ₹220 so Mohit is watching and ready for the entry signal, rather than noticing the stock for the first time at ₹350.

**Validated across all 40 stocks:**
All 7 correctly avoided traps (Cosmo Ferrites, Websol, Megasoft, Servotech, Mercury EV, Magellanic, SPEL) may appear on Turnaround Watch but existing hard blocks prevent any entry. Zero false entries. Rule is information only — hard blocks always take priority.

**Key distinction from pre-profit watchlist:**
- Pre-profit watchlist: company is STILL loss-making but revenue growing >50%. High-risk early-stage.
- Turnaround Watch: company has just turned to first POSITIVE EPS quarter after ≥4 improving quarters. EPS block not yet cleared (needs 2-of-4 confirmed). Entry is close — typically 1–2 quarters away.

```python
def check_earnings_turnaround(symbol, fundamentals, as_of_date):
    """
    Earnings Turnaround Watch — NEW v16.
    
    Fires when a company transitions from loss-making to first
    confirmed profitable quarter, with improving EPS trajectory
    for prior quarters.
    
    This is a MONITORING SIGNAL only. Does NOT generate buy signal.
    Does NOT bypass any hard block.
    Hard blocks still apply when entry signal eventually fires.
    
    Purpose: alert Mohit 1-3 quarters before formal Tier 1/2
    signal is generated. Prevents missing entry on genuine
    turnarounds that are first visible while EPS block still active.
    
    Validated: GE Vernova T&D India — Turnaround Watch fires
    June 2023 at ₹220. Entry signal fires Sep-Oct 2023 at ₹280-320.
    Advanced warning = ~3 months = ₹60-70 per share improvement.
    
    Fires when ALL of the following are true:
    1. EPS was negative in ≥2 of last 8 quarters
       (confirms genuine loss phase, not just one bad quarter)
    2. EPS has been improving monotonically for last 4 quarters
       (confirmed upward trajectory, not a spike)
    3. Most recent announced quarter EPS > 0
       (first positive quarter confirmed)
    4. Revenue growing > TURNAROUND_MIN_REVENUE_GROWTH (10%) YoY
       (business operationally recovering, not just cost-cutting)
    5. Stock NOT yet in eligible universe
       (EPS block still active — 2-of-4 not yet confirmed)
    
    Does NOT fire when:
    - EPS went negative only once (not a real loss phase)
    - EPS trajectory is erratic (not monotonically improving)
    - Revenue is declining (cost-cutting only, not real recovery)
    - Stock is already in eligible universe (EPS block cleared)
    - Any existing hard block was violated in this quarter
      (pledge, SEBI fine, business pivot — turnaround watch
       suppressed for stocks with active hard violations)
    
    IMPORTANT: Turnaround Watch suppressed if hard block active.
    Even if EPS trajectory qualifies, do NOT show on panel if:
    - Pledge > threshold
    - SEBI fine in last 24m
    - Business pivots >= 3 in 5 years
    - OCF negative 3+ of 4 quarters
    Reason: showing these on panel creates psychological pressure
    to override hard blocks. Suppress to prevent temptation.
    """
    if not TURNAROUND_ALERT_ENABLED:
        return False, None

    if not fundamentals or len(fundamentals) < 8:
        return False, None   # insufficient history

    # Condition 1: genuine loss phase — ≥2 of last 8 quarters negative EPS
    last_8q = fundamentals[:8]   # filtered by reporting_date <= as_of_date
    neg_eps_count = sum(1 for q in last_8q if (q.get('eps') or 0) < 0)
    if neg_eps_count < TURNAROUND_HISTORY_QTRS:   # default 2
        return False, None

    # Condition 2: EPS improving monotonically for last 4 quarters
    last_4q_eps = [(q.get('eps') or 0) for q in fundamentals[:4]]
    # Most recent first — check each is better than the next
    is_monotone = all(
        last_4q_eps[i] >= last_4q_eps[i + 1]
        for i in range(len(last_4q_eps) - 1)
    )
    if not is_monotone:
        return False, None

    # Condition 3: most recent quarter EPS > 0
    if last_4q_eps[0] <= 0:
        return False, None

    # Condition 4: revenue growing > 10% YoY
    latest    = fundamentals[0]
    prior_yoy = fundamentals[4] if len(fundamentals) > 4 else None
    if prior_yoy is None:
        return False, None
    rev_now  = latest.get('revenue_cr') or 0
    rev_year = prior_yoy.get('revenue_cr') or 1
    if rev_year <= 0 or (rev_now / rev_year - 1) < TURNAROUND_MIN_REVENUE_GROWTH:
        return False, None

    # Condition 5: EPS block still active (not yet in eligible universe)
    recent_4q      = fundamentals[:4]
    pos_eps_count  = sum(1 for q in recent_4q if (q.get('eps') or 0) > 0)
    if pos_eps_count >= 2:
        return False, None   # already cleared EPS block — handled by main flow

    # Suppress if any current hard block violation
    # Store suppression_reason for audit trail
    stock = get_stock_data(symbol, as_of_date)
    suppression_reason = None

    if stock.get('promoter_pledge_pct', 0) > 50:
        suppression_reason = 'pledge_pct'
    elif stock.get('sebi_fine_last_24m', False):
        suppression_reason = 'sebi_fine_24m'
    elif get_business_pivot_count(symbol, years=5) >= 3:
        suppression_reason = 'business_pivot'

    # OCF check
    recent_ocf     = get_ocf_data_4q(symbol, as_of_date)
    neg_ocf_count  = sum(1 for q in recent_ocf if (q.get('ocf_cr') or 0) < 0)
    if neg_ocf_count >= 3:
        if suppression_reason:
            suppression_reason = 'multiple'
        else:
            suppression_reason = 'ocf_negative'

    if suppression_reason:
        # Log suppressed watch entry for audit trail but do not show on panel
        upsert_turnaround_watch_suppressed(
            symbol             = symbol,
            as_of_date         = as_of_date,
            hard_block_suppressed = True,
            suppression_reason = suppression_reason
        )
        return False, None

    # Calculate consecutive positive EPS quarters (EPS regression detection)
    consecutive_pos = 0
    for q in fundamentals[:4]:
        if (q.get('eps') or 0) > 0:
            consecutive_pos += 1
        else:
            break   # stop at first non-positive quarter

    # Calculate expected entry window
    quarters_to_clearance = 2 - pos_eps_count   # quarters until 2-of-4
    current_price         = get_adj_close(symbol, as_of_date)

    alert = {
        'symbol':                  symbol,
        'alert_type':              'TURNAROUND_WATCH',
        'current_price':           current_price,
        'first_positive_eps':      last_4q_eps[0],
        'eps_improvement_4q':      last_4q_eps[0] - last_4q_eps[3],
        'quarters_to_clearance':   quarters_to_clearance,
        'expected_entry_quarters': quarters_to_clearance,
        'revenue_growth_yoy':      (rev_now / rev_year) - 1,
        'neg_eps_quarters':        neg_eps_count,
        'consecutive_pos_eps':     consecutive_pos,
        'suppression_reason':      None,
        'as_of_date':              as_of_date,
        'note': (
            f"EPS turned positive this quarter after {neg_eps_count} loss quarters. "
            f"EPS block clears in ~{quarters_to_clearance} quarter(s). "
            f"Consecutive positive EPS quarters: {consecutive_pos}. "
            f"Watch for Tier 1/2 entry signal. Hard blocks still active."
        )
    }
    return True, alert


def run_turnaround_watch_scan(db, universe_candidates, as_of_date):
    """
    Runs daily — scans all stocks in eligible universe pool
    (not yet passing hard filters) for turnaround candidates.
    
    Called at pipeline Step 12a before hard filter run.
    Results stored in turnaround_watch table.
    Dashboard panel updated.
    WhatsApp alert sent to Mohit for any NEW turnaround entries.
    """
    alerts = []
    for symbol in get_all_tracked_symbols(db):
        fundamentals = get_fundamentals(db, symbol, as_of_date, limit=8)
        fired, alert = check_earnings_turnaround(symbol, fundamentals, as_of_date)
        if fired:
            alerts.append(alert)
            upsert_turnaround_watch(db, alert)

    # Send WhatsApp for new entries (not already on panel)
    new_alerts = [a for a in alerts if is_new_turnaround_entry(db, a['symbol'], as_of_date)]
    for alert in new_alerts:
        msg = (
            f"🔍 TURNAROUND WATCH — {alert['symbol']}\n"
            f"Price: ₹{alert['current_price']:.0f}\n"
            f"First positive EPS: ₹{alert['first_positive_eps']:.2f}\n"
            f"Entry signal expected: ~{alert['quarters_to_clearance']} quarter(s)\n"
            f"Revenue growth YoY: {alert['revenue_growth_yoy']:.1%}\n"
            f"Action: MONITOR — do NOT enter yet. Hard blocks still active.\n"
            f"Entry triggers when system generates Tier 1/2 signal."
        )
        send_whatsapp(MOHIT_PHONE, msg)

    return alerts
```

**Dashboard panel (UC-17 addition):**
```
┌─────────────────────────────────────────────────────────────────┐
│ 🔍 TURNAROUND WATCH — MONITORING ONLY                           │
│ EPS has turned positive after a loss phase.                     │
│ Entry signal expected within 1–3 quarters.                      │
│                                                                 │
│ ⚠️  DO NOT ENTER any stock on this panel manually.             │
│    Hard blocks still active. Entry ONLY when system             │
│    generates Tier 1 or Tier 2 signal.                           │
│                                                                 │
│ Symbol | Price | First+EPS | Rev Growth | EPS Block Clears In  │
│ GVT&D  | ₹220  | ₹0.42     | +18% YoY   | ~1–2 quarters        │
└─────────────────────────────────────────────────────────────────┘
```

**Entry trigger definition (shown on panel for each stock):**
```
Entry trigger for [SYMBOL]:
  → EPS block clears: 2 of 4 recent quarters positive (reporting_date confirmed)
  → Trend template: all 8 conditions pass
  → VCP base: confirmed breakout with volume
  → Regime: Bull or Strong Bull
When all 4 fire simultaneously → Tier 1 signal generated → normal entry rules apply
```

#### Step 1: Hard Universe Filters (8 Blocks)

```python
def passes_hard_filters(stock, fundamentals, as_of_date):
    """
    8 hard blocks — any one = excluded from universe.
    All validated against named NSE stocks in 40-stock test.
    """
    # Screener.in data gap check — must run FIRST before any block evaluation
    # Missing hard block fields (eps, ocf, pledge) → conservatively exclude
    # See "Known Discrepancies vs v7 — Flaw 6" for full fallback specification
    data_ok, gap_reason = handle_missing_fundamentals(
        stock['symbol'], as_of_date, fundamentals
    )
    if not data_ok:
        return False, gap_reason

    # Block 1: Market cap band
    if not (1000 <= stock['market_cap_cr'] <= 30000):
        return False, 'market_cap_out_of_band'

    # Block 2: Minimum liquidity
    # DEFAULT: ₹15cr (audit-corrected from ₹10cr). Confirm in Test 2.
    if stock['avg_daily_tv_cr'] < MIN_DAILY_TRADED_VALUE_CR:
        return False, 'illiquid'

    # Block 3: Surveillance
    if stock['is_asm'] or stock['is_esm']:
        return False, 'surveillance_list'

    # Block 4: SEBI fraud fine
    if stock['sebi_fine_last_24m']:
        return False, 'sebi_fine'

    # Block 5: IPO age
    if stock['days_listed'] < 200:
        return False, 'ipo_too_recent'

    # Block 6: EPS junk filter
    # CRITICAL: reporting_date <= as_of_date strictly enforced
    recent_4q = get_fundamentals(db, stock['symbol'], as_of_date, limit=4)
    pos_eps_count = sum(1 for q in recent_4q if q['eps'] > 0)
    if pos_eps_count < 2:
        recent_revenue = [q['revenue_cr'] for q in recent_4q if q['revenue_cr']]
        if len(recent_revenue) >= 2:
            rev_growth = (recent_revenue[0] / recent_revenue[-1]) - 1
            if rev_growth > 0.50:
                add_to_preproft_watchlist(stock['symbol'])
        return False, 'eps_junk'

    # Block 7: OCF quality
    recent_ocf = get_ocf_data(db, stock['symbol'], as_of_date, limit=4)
    neg_ocf_count = sum(1 for q in recent_ocf if q['ocf_cr'] < 0)
    if neg_ocf_count >= 3:
        return False, 'persistent_negative_ocf'

    # Block 8: Promoter pledge (split rule)
    pledge_pct  = stock['promoter_pledge_pct'] or 0
    is_infra    = stock['is_infrastructure_sector']
    de_falling  = check_de_falling(stock['symbol'], as_of_date)
    rev_growing = check_revenue_growth(stock['symbol'], as_of_date, min_pct=30)

    if is_infra and de_falling and rev_growing:
        pledge_threshold = 50
    else:
        pledge_threshold = 20

    if pledge_pct > pledge_threshold:
        return False, f'pledge_too_high_{pledge_pct}pct'

    # Block 8b: Business pivot rule
    pivot_count = get_business_pivot_count(stock['symbol'], years=5)
    if pivot_count >= 3:
        return False, 'too_many_business_pivots'

    return True, None
```

#### Step 2: Composite Score Calculation

```python
def build_composite_score(symbol, indicators, universe_indicators,
                          fundamentals, sector_rank, fii_data,
                          dii_data, bulk_deals, as_of_date):

    # Step 1: Normalise momentum factors to 0–100 percentile
    m12_1 = percentile_rank(indicators['mom_12_1'], universe_indicators['mom_12_1'])
    m6m   = percentile_rank(indicators['mom_6m'],   universe_indicators['mom_6m'])
    m3m   = percentile_rank(indicators['mom_3m'],   universe_indicators['mom_3m'])

    # Step 2: Weighted composite (update weights after Backtest Test 1)
    raw_score = (m12_1 * MOM_WEIGHT_12_1) + (m6m * MOM_WEIGHT_6M) + (m3m * MOM_WEIGHT_3M)

    # Step 3: Volatility scaling (Barroso & Santa-Clara 2015)
    actual_vol  = indicators['mom_vol_20d'] * (252**0.5) * 100
    vol_scalar  = min(VOL_TARGET_PCT / actual_vol, VOL_SCALAR_MAX) if actual_vol > 0 else 1.0
    scaled_score = raw_score * vol_scalar

    # Step 4: Fundamental bonus + penalty scores (NOT hard filters)
    f_bonus = calculate_fundamental_bonus(symbol, fundamentals, as_of_date)

    # Step 5: Accumulation bonus scores
    acc_bonus = 0
    if indicators['adl_ratio'] >= 0.60:
        acc_bonus += 4   # A/D ratio bonus

    inst_signal = calculate_smart_institutional_signal(
        symbol, fii_data, dii_data, bulk_deals,
        stock['promoter_holding_pct'],
        stock['is_fii_capped_sector'],
        stock['is_fii_breached']
    )
    if inst_signal:
        acc_bonus += 2

    # Step 6: Sector bonus/penalty
    total_sectors = len(get_all_sectors())
    if sector_rank <= 3:
        sector_bonus = 10
    elif sector_rank >= total_sectors - 2:
        sector_bonus = -5
    else:
        sector_bonus = 0

    # Step 7: Monster score (NEW v12)
    monster_score = calculate_monster_score(symbol, indicators, fundamentals,
                                            sector_rank, as_of_date)

    composite = scaled_score + f_bonus + acc_bonus + sector_bonus
    return composite, scaled_score, vol_scalar, f_bonus, acc_bonus, monster_score
```

#### Step 3: Fundamental Bonus Score Calculation

```python
def calculate_fundamental_bonus(symbol, fundamentals, as_of_date):
    """
    Evidence: Novy-Marx 2015, AQR QMJ, He & Narayanamoorthy 2017.
    Fundamentals as BONUS SCORES — never hard eliminators.
    NSE Momentum 30: zero fundamentals → 19% CAGR. Bonus scores add incremental alpha.
    """
    bonus = 0
    # CRITICAL: ALL fundamentals filtered by reporting_date <= as_of_date
    funds = get_fundamentals(db, symbol, as_of_date, limit=6)
    if not funds: return 0
    latest = funds[0]

    # ── BONUS SIGNALS ────────────────────────────────────────────────
    # Bonus 1: Revenue × OPM simultaneous (+12) — HIGHEST SINGLE SIGNAL
    if len(funds) >= 2:
        rev_growing = latest.get('revenue_cr', 0) > funds[1].get('revenue_cr', 0)
        opm_growing = (latest.get('opm_pct') or 0) > (funds[1].get('opm_pct') or 0)
        if rev_growing and opm_growing:
            bonus += 12

    # Bonus 2: OPM expansion >300bp YoY (+8) — SECTOR NORMALISED (Fix P11)
    if len(funds) >= 5:
        opm_now = latest.get('opm_pct') or 0
        opm_4q  = funds[4].get('opm_pct') or 0
        opm_expansion_abs = opm_now - opm_4q
        sector = get_stock_sector(symbol)
        sector_avg_opm_expansion = get_sector_avg_opm_expansion(sector, as_of_date)
        relative_opm_expansion = opm_expansion_abs - sector_avg_opm_expansion
        if relative_opm_expansion > 2.0:
            bonus += 8
        elif relative_opm_expansion > 1.0:
            bonus += 4

    # Bonus 3: EPS acceleration from low base (+8) — He & Narayanamoorthy 2017
    if len(funds) >= 3:
        g = [f.get('eps_growth_yoy', 0) or 0 for f in funds[:3]]
        if g[0] > g[1] > g[2] and g[0] > 0:
            bonus += 8

    # Bonus 4: Revenue acceleration — SECTOR NORMALISED (Fix P11)
    if len(funds) >= 5:
        rev_now  = latest.get('revenue_cr') or 0
        rev_4q   = funds[4].get('revenue_cr') or 0
        if rev_4q > 0:
            rev_growth_yoy = (rev_now / rev_4q) - 1
            sector = get_stock_sector(symbol)
            sector_avg_rev_growth = get_sector_avg_rev_growth(sector, as_of_date)
            relative_rev_growth = rev_growth_yoy - sector_avg_rev_growth
            if relative_rev_growth >= 0.20:
                bonus += 10
            elif relative_rev_growth >= 0.10:
                bonus += 6
            elif rev_growth_yoy >= 0.30:
                bonus += 4

    # Bonus 5: EPS growth 15%+ (+5) or positive (+2)
    eps_growth = latest.get('eps_growth_yoy', 0) or 0
    if eps_growth >= 15:   bonus += 5
    elif eps_growth >= 0:  bonus += 2

    # Bonus 6: Market cap band crossing trigger (+6)
    days_in_band = get_days_in_mktcap_band(symbol, as_of_date)
    if days_in_band is not None and days_in_band <= 60:
        bonus += 6

    # Bonus 7: Promoter buying open market (+8)
    promoter_buying = check_promoter_buying(symbol, as_of_date, quarters=2)
    if promoter_buying:
        bonus += 8

    # Bonus 8: Low D/E (+2)
    if not latest.get('is_financial', False):
        de = latest.get('debt_to_equity')
        if de is not None and de < 1.5:
            bonus += 2

    # Bonus 9: Post-earnings announcement drift — SUE proxy (v14 UPDATED)
    # Evidence: Bernard & Thomas 1989 + Chan, Jegadeesh & Lakonishok 1996.
    # Uses eps_growth_yoy (Screener.in — already in database, 100% universe coverage).
    # No analyst estimates required. SUE proxy via YoY EPS growth rate.
    # PEAD_ENABLED flag controls whether this fires — set False if signal is noisy.
    if PEAD_ENABLED:
        pead_bonus = calculate_sue_proxy_bonus(symbol, funds, as_of_date)
        bonus += pead_bonus

    # ── PENALTY SIGNALS ──────────────────────────────────────────────
    # Penalty 1: Revenue/profit divergence (−5)
    if len(funds) >= 3:
        rev_trend  = [f.get('revenue_cr', 0) or 0 for f in funds[:3]]
        prof_trend = [f.get('net_profit_cr', 0) or 0 for f in funds[:3]]
        rev_up   = rev_trend[0]  > rev_trend[1]  > rev_trend[2]
        prof_down= prof_trend[0] < prof_trend[1] < prof_trend[2]
        rev_down = rev_trend[0]  < rev_trend[1]  < rev_trend[2]
        prof_up  = prof_trend[0] > prof_trend[1] > prof_trend[2]
        if (rev_up and prof_down) or (rev_down and prof_up):
            bonus -= 5

    # Penalty 2: Other income quality (−5)
    other_income = latest.get('other_income_cr') or 0
    net_profit   = latest.get('net_profit_cr') or 0
    if net_profit > 0 and (other_income / net_profit) > 0.30:
        bonus -= 5

    # Penalty 3: OCF quality check (−5)
    recent_2q = funds[:2]
    low_ocf_count = sum(
        1 for q in recent_2q
        if (q.get('ocf_cr') or 0) > 0 and (q.get('net_profit_cr') or 0) > 0 and
           (q['ocf_cr'] / q['net_profit_cr']) < 0.4
    )
    if low_ocf_count >= 2:
        bonus -= 5

    # Penalty 4: D/E too high (−2)
    if not latest.get('is_financial', False):
        de = latest.get('debt_to_equity')
        if de is not None and de > 3.0:
            bonus -= 2

    # Penalty 5: Promoter selling (−8)
    promoter_selling = check_promoter_selling(symbol, as_of_date, quarters=2)
    if promoter_selling:
        bonus -= 8

    # Penalty 6: SEBI price investigation (−10)
    if stock.get('sebi_investigation_active'):
        bonus -= 10

    # Penalty 7: LODR fine (−3)
    if stock.get('lodr_fine_last_12m'):
        bonus -= 3

    # Penalty 8: Debtors days penalty (−3 or −5)
    debtor_days = latest.get('trade_receivables_days') or 0
    if debtor_days > 180:
        bonus -= 5
    elif debtor_days > 120:
        bonus -= 3

    return min(max(bonus, -20), 30)


def calculate_sue_proxy_bonus(symbol, funds, as_of_date):
    """
    Standardised Unexpected Earnings (SUE) proxy — v14 UPDATED.

    REPLACES: calculate_earnings_surprise_bonus() which required
    analyst_estimate_eps — a field Screener.in Premium does NOT provide.

    Evidence:
      Bernard & Thomas 1989 — SUE predicts post-earnings returns
        even without analyst consensus. The drift is driven by the
        earnings surprise itself, not specifically by the analyst miss.
      Chan, Jegadeesh & Lakonishok 1996 — earnings momentum predicts
        returns. YoY EPS growth is a valid proxy for unexpected earnings.

    Data source: eps_growth_yoy — already in Screener.in Premium.
    Universe coverage: 100%. Zero new data source required.
    Zero operational dependency added.

    Why YoY growth is a valid SUE proxy for NSE mid-caps:
      - Analyst coverage below ₹5,000cr market cap is sparse and stale.
        One analyst covering a stock is not a meaningful consensus.
      - The market implicitly prices in prior-year EPS as the baseline.
        A stock growing EPS 50%+ YoY is a genuine positive surprise
        relative to that implicit expectation — regardless of whether
        an analyst published a formal estimate.
      - Bernard & Thomas showed the drift holds on this basis.

    Bonus/penalty active for PEAD_DRIFT_DAYS (60) trading days
    from reporting_date. After 60 days: bonus expires, returns 0.

    Thresholds (eps_growth_yoy vs same quarter prior year):
      YoY EPS growth > +50%  → +10 for 60 days  (massive positive surprise)
      YoY EPS growth > +25%  → +6  for 60 days  (strong positive surprise)
      YoY EPS growth < -20%  → -8  for 60 days  (significant negative surprise)
      All others              → 0

    Note: this bonus is in ADDITION to Bonus 3 (EPS acceleration) and
    Bonus 5 (EPS growth 15%+). They measure different things:
      Bonus 3 — acceleration trend across 3 quarters (momentum in EPS)
      Bonus 5 — absolute level of YoY growth (15%+ threshold)
      Bonus 9 — large YoY surprise in most recent quarter (drift signal)
    No double-counting risk — thresholds are calibrated to fire
    only on genuinely large YoY moves that are distinct from Bonus 3/5.

    PEAD_ENABLED flag: set False in settings.py to disable this bonus
    entirely if live validation shows it adds noise rather than alpha.
    Test 5 and Test 9 will confirm whether it adds OOS Sharpe.
    """
    if not PEAD_ENABLED:
        return 0

    if not funds or len(funds) < 5:
        return 0   # need 5 quarters for reliable YoY comparison

    latest         = funds[0]
    reporting_date = latest.get('reporting_date')

    if reporting_date is None:
        return 0

    # Check within 60-day drift window
    days_since = (as_of_date - reporting_date).days
    if days_since < 0 or days_since > PEAD_DRIFT_DAYS:
        return 0

    # Use eps_growth_yoy — Screener.in provides this directly
    # This is EPS vs same quarter last year — the correct YoY comparison
    eps_growth = latest.get('eps_growth_yoy') or 0

    # Require both current and prior-year EPS to be positive
    # Avoids distorted ratios when base is loss-making
    eps_now  = latest.get('eps') or 0
    eps_year = funds[4].get('eps') or 0   # same quarter last year
    if eps_now <= 0 or eps_year <= 0:
        return 0

    if eps_growth > 50:     return PEAD_BONUS_LARGE   # +10
    elif eps_growth > 25:   return PEAD_BONUS_SMALL   # +6
    elif eps_growth < -20:  return PEAD_PENALTY        # -8
    return 0
```

#### Step 4: Smart Institutional Flow Signal

```python
def calculate_smart_institutional_signal(symbol, fii_data, dii_data,
                                         bulk_deals, promoter_pct,
                                         is_fii_capped_sector,
                                         is_on_breach_list):
    """
    India-specific: cannot blindly use FII signal for all stocks.
    Problems:
      1. High promoter holding (>65%) leaves little FII headroom
      2. Sectoral FII caps (defence 49%, PSU banks 20%) block FII buying
      3. NSE breach list stocks: FII buying legally blocked
    """
    today = date.today()

    # Case 1: High promoter or FII-capped → bulk deal data only
    if promoter_pct > 75 or is_fii_capped_sector or is_on_breach_list:
        recent_bulk = bulk_deals[
            (bulk_deals['symbol'] == symbol) &
            (bulk_deals['date'] >= today - timedelta(days=10)) &
            (bulk_deals['deal_type'] == 'buy') &
            (bulk_deals['is_institution'] == True)
        ]
        return len(recent_bulk) > 0

    # Case 2: Moderate promoter → DII only
    elif promoter_pct > 65:
        sector = get_stock_sector(symbol)
        dii_sector_flow = dii_data[
            dii_data['sector'] == sector
        ]['dii_net_buy_cr'].tail(5).sum()
        return dii_sector_flow > 0

    # Case 3: Low promoter → FII + DII combined
    else:
        sector    = get_stock_sector(symbol)
        fii_flow  = fii_data[fii_data['sector'] == sector]['fii_net_buy_cr'].tail(5).sum()
        dii_flow  = dii_data[dii_data['sector'] == sector]['dii_net_buy_cr'].tail(5).sum()
        return (fii_flow + dii_flow) > 0
```

#### Step 5: Monster Stock Detection (NEW v12)

**Theoretical basis:** Bessembinder 2018 — the distribution of individual stock returns is extremely right-skewed. The top 4% of stocks account for all net wealth creation in the stock market. A disproportionate share of total portfolio alpha comes from identifying these stocks early and holding them through their full run. The Monster Stock Detection Layer is the systematic operationalisation of this finding: detect the profile of a potential wealth-creation outlier at entry and apply asymmetric hold rules throughout the position lifecycle.

**John Boik framework:** Monster stocks share a common pre-breakout profile — sector leadership, accelerating fundamentals over multiple consecutive quarters, repeated consolidation patterns as institutional accumulation builds, and exceptionally smooth price trends reflecting sustained demand.

```python
def calculate_monster_score(symbol, indicators, fundamentals,
                            sector_rank, as_of_date):
    """
    Monster Stock Score (0–100).
    Evidence: Bessembinder 2018 — top 4% of stocks drive all net market wealth.
    Framework: John Boik — common profile of monster stocks before major runs.

    If score >= 80: position managed under Phase 4 exit rules
    regardless of actual gain realised. This is the most aggressive
    hold override in the system. Justified by Bessembinder: cutting
    a monster early destroys alpha that cannot be recovered.

    Scoring criteria:
      RS rank >= 90th percentile          +25
      Consolidation count >= 3            +20
      mom_quality >= 0.70                 +20
      Sector rank #1                      +15
      Sustained EPS acceleration 4+qtrs  +10
      Base depth contracting              +10
                                   Max = 100
    """
    score = 0

    # Criterion 1: RS rank >= 90th percentile (+25)
    # True market leaders are in the top 10% — not just top 30%
    rs_rank = indicators.get('rs_rank', 0)
    if rs_rank >= 90:
        score += 25

    # Criterion 2: Consolidation count >= 3 (+20)
    # Multiple prior bases = repeated institutional accumulation
    # Each new base on top of the prior = higher-conviction hold
    consolidation_count = get_historical_consolidation_count(symbol, as_of_date)
    if consolidation_count >= 3:
        score += 20

    # Criterion 3: Momentum quality >= 0.70 (+20)
    # 70%+ of weekly closes positive = exceptionally smooth uptrend
    # Smooth uptrends = institutional demand, not retail chasing
    mom_quality = indicators.get('mom_quality', 0)
    if mom_quality >= 0.70:
        score += 20

    # Criterion 4: Sector rank #1 (+15)
    # Monster stocks lead their sector. Sector #1 = only the best.
    if sector_rank == 1:
        score += 15

    # Criterion 5: Sustained EPS acceleration 4+ consecutive quarters (+10)
    # He & Narayanamoorthy 2017 — earnings acceleration predicts returns.
    # Sustained = not a one-quarter fluke. 4 quarters = real business acceleration.
    funds = get_fundamentals(db, symbol, as_of_date, limit=5)
    if len(funds) >= 4:
        eps_acc_qtrs = 0
        for i in range(len(funds) - 1):
            g_now  = funds[i].get('eps_growth_yoy', 0) or 0
            g_prev = funds[i+1].get('eps_growth_yoy', 0) or 0
            if g_now > g_prev and g_now > 0:
                eps_acc_qtrs += 1
            else:
                break  # must be consecutive
        if eps_acc_qtrs >= 4:
            score += 10

    # Criterion 6: Base depth contracting (+10)
    # Each successive base shallower than the last = overhead supply absorbed.
    # Validated: Tanla, Deepak Nitrite, Force Motors — each new base shallower.
    depths = get_historical_base_depths(symbol, as_of_date)
    if len(depths) >= 2 and all(depths[i] < depths[i-1] for i in range(1, len(depths))):
        score += 10

    # Criterion 7: Sector outperformance 2× or more over prior 6 months (+10) — NEW v13
    # Tests true sector leadership, not just absolute momentum.
    # Stock must outperform its sector index by MONSTER_SECTOR_OUTPERFORM_MULT (2.0×)
    # over the prior 6 months (126 trading days).
    # Note: this is a scoring BONUS, not a hard gate. Some genuine monster stocks
    # underperform their sector early before the main breakout. A hard gate would
    # exclude early-stage leaders before they have fully separated from the pack.
    sector_return_6m = get_sector_index_return(
        get_stock_sector(symbol), as_of_date, lookback_days=126
    )
    stock_return_6m  = indicators.get('mom_6m', 0)
    if sector_return_6m > 0 and stock_return_6m > 0:
        outperform_ratio = stock_return_6m / sector_return_6m
        if outperform_ratio >= MONSTER_SECTOR_OUTPERFORM_MULT:
            score += MONSTER_SECTOR_OUTPERFORM_BONUS    # +10

    return min(score, 100)   # cap at 100 — new criterion does not raise the max


def is_monster_candidate(monster_score):
    """
    Returns True if monster score >= MONSTER_SCORE_THRESHOLD (default 80).
    Score threshold alone does NOT activate Phase 4 override — see gain gate below.
    """
    return monster_score >= MONSTER_SCORE_THRESHOLD
```

**Monster score application (v13 — gain-gated override):**

```python
# In calculate_exit_signal() — Phase override
# Applied BEFORE phase determination, not inside each phase block.
#
# v13 FIX: Monster override now requires BOTH score >= 80 AND gain >= 40%.
# At gain < 40%: monster score is tracked and displayed but does NOT change
# exit phase. The position must prove itself before Phase 4 loose exits apply.
#
# Rationale: early monster classification is uncertain. Many stocks score high
# on entry profile (RS rank, sector leadership, trend quality) but fail due to
# sector rotation or failed breakout. Requiring 40% gain confirmation means the
# stock has demonstrated real price strength before we apply the loosest exits.

monster_score = get_current_monster_score(position['symbol'], as_of_date)
effective_gain = gain

if (is_monster_candidate(monster_score) and
        gain >= MONSTER_OVERRIDE_MIN_GAIN):
    # Both conditions met — apply Phase 4 exit rules regardless of actual gain
    effective_gain = max(gain, 2.01)   # force into Phase 4 block
    # Log that monster override is active
    position['monster_override_active'] = True
else:
    # Score tracked but override not yet active
    # Will activate automatically once gain crosses MONSTER_OVERRIDE_MIN_GAIN
    position['monster_override_active'] = False

# Continue with effective_gain in exit logic below
```

---

### UC-05: Trend Template Screening (Engine B — Step 1)

All 8 conditions are hard gates — any failure = excluded from signal generation.

| # | Condition | Code |
|---|---|---|
| 1 | Price > MA50 | `adj_close > ma50` |
| 2 | Price > MA150 | `adj_close > ma150` |
| 3 | Price > MA200 | `adj_close > ma200` |
| 4 | MA50 > MA150 | `ma50 > ma150` |
| 5 | MA150 > MA200 | `ma150 > ma200` |
| 6 | MA200 slope rising | `ma200_slope > 0` |
| 7 | Within 20% of 52W high | `adj_close >= week52_high * 0.80` |
| 8 | Stage 2 established | 20+ consecutive trading days above MA200 |

Evidence: Every profitable catch in the 40-stock test required Stage 2 entry. Zero profitable catches came from non-Stage 2 entries. Backtest Test 4 will determine if 20% or 25% is better for Condition 7 on NSE specifically.

---

### UC-06: Pattern Detection (Engine B — Step 2)

**Pattern 1 — VCP (Full Mathematical Definition)**

```python
def detect_vcp(symbol, prices, volumes, as_of_date):
    """
    Volatility Contraction Pattern — Minervini definition.
    Requires: prior uptrend, 3+ contractions shrinking in depth and time,
    volume declining through base, OBV rising during base.
    """
    # Step 1: Find base start (most recent pivot high)
    recent_252  = prices.tail(252)
    pivot_high  = recent_252['adj_close'].max()
    base_start  = recent_252['adj_close'].idxmax()
    base_prices = prices.loc[base_start:]

    # Step 2: Validate base length
    base_weeks = len(base_prices) / 5
    if base_weeks < 5 or base_weeks > 52:
        return None

    # Step 3: Validate overall depth
    depth_overall = (pivot_high - base_prices['adj_close'].min()) / pivot_high
    if depth_overall > 0.40:
        return None

    # Step 4: Extract contractions and validate
    contractions = find_contractions(base_prices)
    if len(contractions) < 3:
        return None

    depths = [c['depth_pct'] for c in contractions]
    if not all(depths[i] < depths[i-1] for i in range(1, len(depths))):
        return None

    avg_vols = [c['avg_volume'] for c in contractions]
    if avg_vols[-1] >= avg_vols[0]:
        return None

    # Step 5: NSE circuit exclusion
    if had_circuit_lock(symbol, base_prices.index):
        return None

    # Step 6: OBV slope during base — CRITICAL SCOPE RULE
    base_vols   = volumes.loc[base_start:]
    base_closes = base_prices['adj_close']
    sign        = base_closes.diff().apply(lambda x: 1 if x>0 else (-1 if x<0 else 0))
    obv_base    = (sign * base_vols).cumsum()
    obv_slope   = np.polyfit(range(len(obv_base)), obv_base, 1)[0]
    obv_bonus   = 5 if obv_slope > 0 else 0

    # OBV bullish divergence
    price_makes_lower_low = base_prices['adj_close'].tail(20).min() < \
                            base_prices['adj_close'].iloc[20:40].min()
    obv_makes_higher_low  = obv_base.tail(20).min() > obv_base.iloc[20:40].min()
    obv_divergence        = price_makes_lower_low and obv_makes_higher_low

    # Step 6b: ATR compression check
    atr_now         = calculate_atr(base_prices.tail(14), 14)
    atr_early       = calculate_atr(base_prices.head(14), 14)
    atr_compression = atr_now / atr_early if atr_early > 0 else 1.0
    vcp_quality_bonus = 2 if atr_compression < 0.60 else (1 if atr_compression < 0.75 else 0)

    # Step 7: Pivot and entry zone
    pivot = contractions[-1]['high']
    return {
        'pattern_type':        'VCP',
        'pivot_price':         pivot,
        'stop_loss':           base_prices['adj_close'].min(),
        'entry_zone_low':      pivot,
        'entry_zone_high':     pivot * 1.03,
        'base_length_days':    len(base_prices),
        'base_depth_pct':      depth_overall,
        'contraction_count':   len(contractions),
        'obv_slope':           obv_slope,
        'obv_bonus':           obv_bonus,
        'obv_divergence':      obv_divergence,
        'atr_compression':     atr_compression,
        'vcp_quality_bonus':   vcp_quality_bonus,
    }
```

> **Fix P9 — VCP UNIT TESTING REQUIREMENT:** The `find_contractions()` function must be validated against 50+ confirmed historical VCP patterns before any backtest. Detection rate ≥ 80% on confirmed patterns. False positive rate ≤ 10% on non-VCP stocks. If either threshold fails, revise `find_contractions()` before proceeding.

**Entry Rules — All Must Pass**

```python
def check_entry_valid(signal, today_bar, next_day_open=None, as_of_date=None):
    # Condition 1: Price closed above pivot
    if today_bar['adj_close'] <= signal['pivot_price']:
        return False, 'no_breakout'

    # Condition 2: Volume expansion
    if today_bar['vol_ratio_50'] < 1.5:
        return False, 'insufficient_volume'

    # Condition 3: Strong close (not a reversal bar)
    day_range = today_bar['high'] - today_bar['low']
    if day_range > 0:
        close_pos = (today_bar['adj_close'] - today_bar['low']) / day_range
        if close_pos < 0.75:
            return False, 'weak_close'

    # Condition 4: Not too extended above pivot
    if today_bar['adj_close'] > signal['pivot_price'] * 1.05:
        return False, 'too_extended'

    # Condition 5: Circuit check
    if today_bar.get('hit_upper_circuit', False):
        return False, 'upper_circuit'

    # Condition 6: Earnings safety rule
    days_to_results = get_days_to_next_results(signal['symbol'], as_of_date)
    if days_to_results is not None and days_to_results <= 10:
        return False, 'earnings_too_close'

    # Condition 7: Max entry price rule
    if next_day_open is not None:
        if next_day_open > signal['pivot_price'] * (1 + MAX_ENTRY_ABOVE_PIVOT):
            return False, 'gap_too_large_signal_expired'

    return True, None
```

**False Breakout Filter**

```python
def update_pending_signals(db, as_of_date):
    """
    40–60% of NSE breakouts fail within 2 days.
    Day 1: breakout detected → signal status = 'Pending'
    Day 2: price holds above pivot → status = 'Confirmed' → enters watchlist
           price falls below pivot → status = 'Failed' → discarded
    Only 'Confirmed' signals appear in Tier 1 watchlist.
    """
    for signal in get_pending_signals(db):
        current_price = get_adj_close(db, signal['symbol'], as_of_date)
        if current_price > signal['pivot_price']:
            update_signal_status(signal['id'], 'Confirmed', as_of_date)
        else:
            update_signal_status(signal['id'], 'Failed', as_of_date)
```

---

### UC-07: Position Sizing (Engine C — Layer 7)

```python
def calculate_position_size(portfolio_value, regime_params,
                            signal, stock, portfolio_vol_scalar):
    """
    2% risk rule: risk amount / risk per share = shares to buy.
    Multiple adjustment factors applied in sequence.
    """
    base_risk_pct = regime_params['risk_pct']
    adj_risk_pct  = base_risk_pct * portfolio_vol_scalar

    entry_mid  = (signal['entry_zone_low'] + signal['entry_zone_high']) / 2
    risk_per_sh = entry_mid - signal['stop_loss']
    if risk_per_sh <= 0:
        return None

    risk_amount = portfolio_value * (adj_risk_pct / 100)
    shares      = int(risk_amount / risk_per_sh)
    pos_value   = shares * entry_mid
    pos_pct     = pos_value / portfolio_value

    pos_pct = min(pos_pct, 0.20)
    pos_pct = max(pos_pct, 0.02)
    shares  = int(pos_pct * portfolio_value / entry_mid)

    # Adjustment 1: Beta-based size reduction
    if stock.get('beta_1yr', 1.0) > BETA_HIGH_THRESHOLD:
        shares  = int(shares * BETA_SIZE_REDUCTION)
        pos_pct = shares * entry_mid / portfolio_value

    # Adjustment 2: Thin float rule
    is_psu   = stock.get('is_psu', False)
    prom_pct = stock.get('promoter_holding_pct', 0)
    if not is_psu and prom_pct > THIN_FLOAT_PROMOTER_PCT:
        bulk_confirmed = check_recent_bulk_deal(stock['symbol'])
        if not bulk_confirmed:
            return None
        shares = int(shares * BETA_SIZE_REDUCTION)

    # Adjustment 3: Correlation-aware size reduction (NEW v14)
    # Reduces size when new position is highly correlated with existing holdings.
    # Prevents hidden concentration risk during sector rotations where portfolio
    # heat appears normal but correlated drawdown is 2-3× model prediction.
    corr_adjusted_shares, corr_adj_applied = calculate_correlation_adjusted_size(
        symbol        = signal['symbol'],
        open_positions = open_positions,
        price_df      = price_df,
        base_shares   = shares
    )
    shares         = corr_adjusted_shares
    pos_pct        = shares * entry_mid / portfolio_value

    return {
        'shares':              shares,
        'position_value':      shares * entry_mid,
        'position_pct':        shares * entry_mid / portfolio_value,
        'risk_amount':         risk_amount,
        'entry_price':         entry_mid,
        'correlation_adj_applied': corr_adj_applied,   # NEW v14: logged to open_positions
    }


def calculate_correlation_adjusted_size(symbol, open_positions,
                                         price_df, base_shares,
                                         lookback=60):
    """
    Correlation-aware position sizing — NEW v14.

    Reduces position size when the new stock is highly correlated
    with any existing holding over the prior 60 trading days.

    Rationale: momentum portfolios cluster in leading sectors.
    During crashes, intra-portfolio correlations spike to 0.80-0.95.
    Portfolio heat (risk-per-trade sum) does not capture this.
    A 15-stock momentum portfolio in a crash can behave like
    3-4 concentrated positions. Correlation adjustment pre-empts this.

    Rules:
      max_corr > 0.85 with any single holding → 50% size reduction
      max_corr > 0.70 with any single holding → 25% size reduction
      max_corr <= 0.70                         → no adjustment

    Correlation measured on daily returns (adj_close pct_change).
    Minimum 30 overlapping days required — if fewer, no adjustment.

    Returns: (adjusted_shares, corr_adj_applied)
    """
    new_returns = (
        price_df[price_df['symbol'] == symbol]['adj_close']
        .pct_change()
        .tail(lookback)
        .dropna()
    )

    max_corr        = 0.0
    corr_adj_applied = False

    for pos in open_positions:
        if not pos.get('is_active', True):
            continue
        existing_returns = (
            price_df[price_df['symbol'] == pos['symbol']]['adj_close']
            .pct_change()
            .tail(lookback)
            .dropna()
        )
        # Align on common index
        aligned = new_returns.align(existing_returns, join='inner')[0]
        if len(aligned) < 30:
            continue   # insufficient overlap — skip, no adjustment
        corr     = new_returns.loc[aligned.index].corr(
                   existing_returns.loc[aligned.index])
        max_corr = max(max_corr, abs(corr))

    if max_corr > CORR_HIGH_THRESHOLD:      # > 0.85
        adjusted  = int(base_shares * CORR_SIZE_HIGH_REDUCTION)   # 50%
        corr_adj_applied = True
    elif max_corr > CORR_MED_THRESHOLD:     # > 0.70
        adjusted  = int(base_shares * CORR_SIZE_MED_REDUCTION)    # 75%
        corr_adj_applied = True
    else:
        adjusted = base_shares

    return adjusted, corr_adj_applied


def check_portfolio_constraints(new_signal, open_positions, portfolio_value, regime):
    """
    v13: Portfolio heat is now regime-dependent.
    Strong Bull 6% / Bull 5% / Weak 4% / Bear 2% / Full Bear 0%.
    Previous flat 4% was under-allocating during strong bull markets
    where momentum concentration is the primary source of alpha.
    """
    # Regime-dependent heat limit (NEW v13)
    heat_limits = {
        'Strong Bull': HEAT_STRONG_BULL / 100,   # 0.06
        'Bull':        HEAT_BULL / 100,           # 0.05
        'Weak':        HEAT_WEAK / 100,           # 0.04
        'Bear':        HEAT_BEAR / 100,           # 0.02
        'Full Bear':   0.0,
    }
    max_heat = heat_limits.get(regime, HEAT_WEAK / 100)  # default to Weak if unknown

    current_heat = sum(
        p['value'] * (p['entry'] - p['stop']) / p['entry']
        for p in open_positions
    ) / portfolio_value
    new_heat = new_signal['risk_amount'] / portfolio_value

    if current_heat + new_heat > max_heat:
        return False, f'portfolio_heat_exceeded_{regime}'

    sector_total = sum(
        p['value'] for p in open_positions
        if p['sector'] == new_signal['sector']
    )
    if (sector_total + new_signal['position_value']) / portfolio_value > MAX_SECTOR_CONC / 100:
        return False, 'sector_concentration_exceeded'

    return True, None
```

---

### UC-08: Watchlist Generation

**Output fields per stock:**

| Field | Description |
|---|---|
| rank | 1–20 by composite score |
| symbol | NSE ticker |
| tier | 1=Buy Now / 2=Near Pivot / 3=On Radar |
| composite_score | Full score including all bonuses and penalties |
| momentum_score | Pure momentum component (before bonuses) |
| vol_scalar | Volatility scaling factor applied |
| fundamental_bonus | Total fundamental bonus/penalty points |
| obv_bonus | OBV slope bonus (0 or 5) |
| obv_divergence | Boolean — bullish OBV divergence detected |
| adl_ratio | 20-day accumulation/distribution ratio |
| delivery_trend | Rising/Flat/Falling — display context only, never scored |
| inst_flow_signal | Which signal used: FII / DII / BulkDeal |
| inst_flow_positive | Boolean — institutional signal positive |
| pattern_type | VCP / TightBase / Breakout |
| status | Confirmed / Pending / Forming |
| entry_zone | Low–High price range |
| stop_loss | Base low price |
| suggested_size_pct | % of portfolio (from UC-07) |
| earnings_date | Next results date |
| days_to_earnings | Trading days until next results |
| earnings_flag | True if results due within 10 days |
| regime | Current regime name |
| large_cap_warning | True if market cap approaching ₹30,000cr ceiling |
| **monster_score** | **0–100 monster stock score (NEW v12)** |
| **is_monster_candidate** | **True if monster_score >= 80 (NEW v12)** |

**Tier assignment logic:**

```python
def assign_tier(signal, composite_score, days_to_earnings):
    if (signal['status'] == 'Confirmed' and
        regime in ['Bull', 'Strong Bull'] and
        composite_score >= 70):
        tier = 1
    elif (signal['pct_from_pivot'] <= 0.03 and
          composite_score >= 65 and
          signal['base_length_days'] >= 25):
        tier = 2
    elif composite_score >= 55:
        tier = 3

    if days_to_earnings is not None and days_to_earnings <= 10:
        tier = max(tier, 3)

    return tier
```

**Monster Candidates Panel (NEW v12):**

A separate panel below the main watchlist showing all stocks with `monster_score >= 60` regardless of tier. This panel is for monitoring — not immediate action. Stocks graduate from the monster panel to the main watchlist when they generate a confirmed Tier 1 or Tier 2 signal. Dashboard label: **"Monster Watch — Potential Outlier Candidates (Bessembinder 2018)"**

Panel fields: `symbol`, `monster_score`, `is_monster_candidate`, `rs_rank`, `consolidation_count`, `mom_quality`, `sector_rank`, `eps_acc_quarters`, `base_depth_contracting`, `composite_score`, `tier`.

---

### UC-08B: Monthly Rebalancing Logic (NEW v14)

**Purpose:** Define the exact decision rules executed on the last trading day of each calendar month. Previously, Test 8 tested rebalancing *frequency* but the *logic* of what happens during a rebalance was never specified. This is a missing implementation definition — a developer building from v13 would have had no specification for what rebalancing actually does.

**Trigger:** Last trading day of each month, after daily pipeline completes. Runs after exit signals are checked but before new entry signals are executed.

**Five-step sequence — execute in order, never reorder:**

```python
def monthly_rebalance(open_positions, watchlist, portfolio_value,
                      regime, as_of_date, price_df):
    """
    Monthly rebalancing — NEW v14.
    Runs on last trading day of each month after daily exit engine.

    Step 1: Confirm all RS persistence exits are current.
    Step 2: Trim positions that have grown above MAX_POSITION_PCT.
    Step 3: Do NOT top up shrunken positions — partial exits were intentional.
    Step 4: Fill empty regime slots from Tier 1 watchlist only.
    Step 5: Flag (do not auto-swap) positions whose score has dropped vs new Tier 1.

    Returns list of actions to execute at next day open.
    """
    actions = []

    # ── STEP 1: Confirm RS persistence exits ─────────────────────────
    # Daily exit engine handles this. Monthly rebalance confirms no
    # position was missed. Log any mismatch as data integrity issue.
    for pos in open_positions:
        if pos.get('rs_below_floor_weeks', 0) >= RS_PERSIST_WEEKS:
            if pos['is_active']:
                actions.append({
                    'symbol': pos['symbol'],
                    'action': 'FULL_EXIT',
                    'reason': 'monthly_rebalance_rs_persist_confirm'
                })

    # ── STEP 2: Trim oversized positions ─────────────────────────────
    # Positions grow above MAX_POSITION_PCT when price appreciates.
    # Uncapped winners create hidden concentration risk.
    # Trim to MAX_POSITION_PCT at month end — not aggressively, not daily.
    # This is NOT a profit-taking rule — it is a concentration control.
    for pos in open_positions:
        if not pos.get('is_active', True):
            continue
        current_price   = get_current_price(price_df, pos['symbol'], as_of_date)
        current_value   = pos['shares'] * current_price
        current_pct     = current_value / portfolio_value

        if current_pct > MAX_POSITION_PCT / 100:
            target_value  = (MAX_POSITION_PCT / 100) * portfolio_value
            excess_value  = current_value - target_value
            excess_shares = int(excess_value / current_price)
            if excess_shares > 0:
                actions.append({
                    'symbol':      pos['symbol'],
                    'action':      'TRIM_OVERSIZE',
                    'sell_shares': excess_shares,
                    'reason':      'monthly_rebalance_trim_oversize'
                })

    # ── STEP 3: Do NOT top up shrunken positions ─────────────────────
    # If a position has shrunk below MIN_POSITION_PCT because of partial exits
    # (climax run, 21DMA confirms, ATH crystallisation), do NOT add back.
    # The system reduced the position for a reason.
    # Topping up automatically reverses a deliberate risk decision.
    # Only exception: if position shrank due to fast crash reduction
    # AND fast_crash_active is now False AND regime is Bull or Strong Bull:
    #   → flag for manual review only, never auto-restore.
    # No code — this step is a prohibition, not an action.

    # ── STEP 4: Fill empty regime slots from Tier 1 only ────────────
    # Never fill empty slots from Tier 2 or Tier 3 during rebalance.
    # If no Tier 1 signals exist: leave slots empty. Cash is a position.
    max_positions   = regime.get('max_positions', 12)
    active_count    = len([p for p in open_positions if p.get('is_active', True)])
    slots_available = max(0, max_positions - active_count)

    tier1_candidates = [
        w for w in watchlist
        if w['tier'] == 1
        and w['symbol'] not in [p['symbol'] for p in open_positions if p.get('is_active')]
    ]

    for signal in tier1_candidates[:slots_available]:
        actions.append({
            'symbol': signal['symbol'],
            'action': 'NEW_ENTRY',
            'reason': 'monthly_rebalance_fill_slot',
            'signal_id': signal['signal_id']
        })

    # ── STEP 5: Flag score degradation for manual review ────────────
    # If an existing position's composite_score has dropped >15 points
    # AND a new Tier 1 signal has composite_score > existing + 15:
    # FLAG for manual review. Do NOT auto-swap.
    # Rationale: an auto-swap based on composite score alone would
    # systematically exit late-phase winners (lower RS, lower momentum
    # because they already ran) in favour of earlier-stage setups.
    # Human judgment is required to distinguish deterioration from
    # normal late-phase score compression.
    current_scores = {p['symbol']: get_current_composite_score(p['symbol'], as_of_date)
                      for p in open_positions if p.get('is_active', True)}

    for pos_sym, pos_score in current_scores.items():
        for signal in tier1_candidates:
            if signal['composite_score'] > pos_score + REBALANCE_SWAP_FLAG_THRESHOLD:
                actions.append({
                    'symbol':          pos_sym,
                    'action':          'FLAG_MANUAL_REVIEW',
                    'reason':          'monthly_rebalance_score_degradation',
                    'incumbent_score': pos_score,
                    'challenger':      signal['symbol'],
                    'challenger_score': signal['composite_score']
                })
                break  # one flag per position per month

    return actions
```

**Rebalancing action execution:** All actions from `monthly_rebalance()` are queued and executed at the next trading day's open price — never at the close of the rebalance day. `TRIM_OVERSIZE` and `FULL_EXIT` execute first. `NEW_ENTRY` executes second. `FLAG_MANUAL_REVIEW` generates a dashboard alert and WhatsApp notification — no automatic trade.

**Rebalancing log:** All monthly rebalance actions stored in `performance_log` with `exit_reason` or entry tagged `monthly_rebalance_*` for attribution analysis.

---

**Core principle:** Exit tightness is a function of gain already captured, not a fixed rule applied uniformly. Jegadeesh & Titman 1993: momentum profits accrue over 6–12 months — cutting early destroys most alpha. Grinblatt & Moskowitz 2004: consistent uptrend = hold signal. AQR: RS rank decay is the primary "momentum ended" signal. **Bessembinder 2018 (v12):** top 4% of stocks drive all net market wealth creation — the cost of cutting a monster stock early is asymmetrically large.

**10/21 DMA removed as exit trigger.** Tanla (₹220→₹1,100) and Force Motors (₹2,500→₹26,450) both had multiple 10/21 DMA violations along the way. A strict 10/21 DMA rule exits at 2–3x when these go on to 5–10x. The 10-week MA is used only as a floor reference in Phase 4 — not as an exit trigger.

**MA200 is the backstop, not the primary exit.** If phase-based exits are working, MA200 should rarely fire.

#### Supporting Helper Functions (v12 + v13)

**check_trend_integrity (NEW v12)**

```python
def check_trend_integrity(symbol, price_df, lookback=20):
    """
    Higher highs / higher lows check over the most recent lookback days.
    Purpose: distinguish genuine pullbacks (trend intact) from distribution
             (trend broken). Applied as override layer on 21DMA logic in
             Phase 2 and Phase 3.

    INTACT:  most recent swing high > prior swing high
             AND most recent swing low > prior swing low
    BROKEN:  most recent swing high < prior swing high
             OR most recent swing low < prior swing low

    If INTACT: suppress 21DMA counter even on average volume.
    If BROKEN: confirm exit signals regardless of volume.
    """
    prices = price_df[price_df['symbol']==symbol]['adj_close'].tail(lookback)

    # Identify swing highs and lows using simple local extrema
    swing_highs = []
    swing_lows  = []
    for i in range(1, len(prices) - 1):
        if prices.iloc[i] > prices.iloc[i-1] and prices.iloc[i] > prices.iloc[i+1]:
            swing_highs.append(prices.iloc[i])
        if prices.iloc[i] < prices.iloc[i-1] and prices.iloc[i] < prices.iloc[i+1]:
            swing_lows.append(prices.iloc[i])

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return 'UNKNOWN'  # insufficient data — do not override either way

    hh = swing_highs[-1] > swing_highs[-2]   # higher high
    hl = swing_lows[-1]  > swing_lows[-2]    # higher low

    if hh and hl:
        return 'INTACT'
    elif not hh or not hl:
        return 'BROKEN'
    else:
        return 'NEUTRAL'
```

**Volume direction during pullbacks (NEW v12)**

```python
def classify_pullback_volume(position, current_price, indicators):
    """
    Applied when price is below 21DMA — determines whether the pullback
    is healthy (low volume = no selling pressure) or distribution
    (high volume = institutional exit).

    vol_ratio < 0.75  → LOW VOLUME pullback  → hold override
                         Reset ma21_below_count to 0.
                         Dry-up in volume on a pullback = classic re-accumulation.
                         Do not penalise — this is the desired pattern.

    vol_ratio >= 1.5  → HIGH VOLUME breakdown → instant distribution confirm
                         Reduce 25% immediately.
                         No need to wait for MA21_CONFIRM_DAYS.
                         High volume below 21DMA = institutional selling confirmed.

    0.75 <= vol_ratio < 1.5 → AVERAGE VOLUME → standard 21DMA counter applies.
                              Increment ma21_below_count as normal.
                              Trend integrity check is the additional filter (below).
    """
    vol_ratio = indicators.get('vol_ratio_20', 1.0)

    if vol_ratio < PULLBACK_LOW_VOL_THRESHOLD:
        return 'LOW_VOLUME_HOLD_OVERRIDE'
    elif vol_ratio >= PULLBACK_HIGH_VOL_THRESHOLD:
        return 'HIGH_VOLUME_INSTANT_CONFIRM'
    else:
        return 'AVERAGE_VOLUME_USE_COUNTER'
```

**check_atr_compressing — Time Stop Suppression (NEW v13)**

```python
def check_atr_compressing(position, indicators):
    """
    Suppresses the time stop if ATR is compressing relative to ATR at entry.
    Purpose: a flat price with shrinking volatility is a coiling base, not
             a dead trade. Exiting on time stop here would remove a slow-building
             leader before the main expansion begins.

    Condition:
      atr_now < atr_entry * ATR_COMPRESS_SUPPRESS_RATIO

    Where ATR_COMPRESS_SUPPRESS_RATIO = 0.70 (LOCKED).
    Means: current ATR must be < 70% of entry ATR to suppress time stop.
    A 30%+ compression in daily range = genuine coiling action.

    Returns True if ATR is compressing (time stop should be suppressed).
    Returns False if ATR is not compressing (time stop fires normally).
    """
    atr_now   = indicators.get('atr14', None)
    atr_entry = position.get('atr_at_entry', None)

    if atr_now is None or atr_entry is None or atr_entry <= 0:
        return False  # insufficient data — time stop fires normally

    return (atr_now / atr_entry) < ATR_COMPRESS_SUPPRESS_RATIO
```

**check_rs_persistence — RS Persistence Filter (NEW v13)**

```python
def check_rs_persistence(position, rs_rank, rs_floor):
    """
    RS persistence filter — NEW v13.
    Replace single-day RS exit with 4-consecutive-week persistence requirement.

    Market leaders frequently experience temporary RS rank drops during
    consolidation. A single week below the floor is noise. Four consecutive
    weeks below the floor = genuine momentum breakdown.

    Logic:
      - Track rs_below_floor_weeks counter on the position
      - Increment by 1 each week the RS rank remains below rs_floor
      - Reset to 0 immediately if RS rank recovers above rs_floor
      - Exit only when rs_below_floor_weeks >= RS_PERSIST_WEEKS (default 4)

    Note: counter is weekly, not daily. Check on Friday close (or last
    trading day of each week) only. Daily checks would be too sensitive.

    Exception — total RS collapse: RS rank < 20 remains a daily hard exit
    (already handled in mandatory overrides — this filter does NOT apply there).
    """
    # Recover if RS rank is back above floor
    if rs_rank >= rs_floor:
        position['rs_below_floor_weeks'] = 0
        return False   # no exit

    # Below floor — check if this is a weekly check day
    # Implementation: caller passes is_weekly_check_day flag
    # Only increment on weekly check to avoid daily noise
    if position.get('is_weekly_check_day', False):
        position['rs_below_floor_weeks'] = position.get('rs_below_floor_weeks', 0) + 1

    if position.get('rs_below_floor_weeks', 0) >= RS_PERSIST_WEEKS:
        position['rs_below_floor_weeks'] = 0
        return True   # 4 consecutive weeks below floor — exit

    return False   # still within tolerance window
```

#### Full Exit Signal Function (v13)

```python
def calculate_exit_signal(position, price_df, indicators, regime,
                          universe_rs_ranks, as_of_date):

    current_price   = get_adj_close(price_df, position['symbol'], as_of_date)
    gain            = (current_price / position['entry_price']) - 1
    recent_10w_high = price_df[position['symbol']].tail(50)['adj_close'].max()
    ma50            = indicators['ma50']
    ma200           = indicators['ma200']
    ma21            = indicators['ma21']
    rs_rank         = universe_rs_ranks.get(position['symbol'], 50)

    # ── MONSTER STOCK OVERRIDE (v13 — gain-gated) ────────────────────
    # Bessembinder 2018: top 4% of stocks drive all net wealth creation.
    # v13 FIX: override requires score >= 80 AND gain >= 40%.
    # Below 40% gain: score tracked but no phase change.
    monster_score  = get_current_monster_score(position['symbol'], as_of_date)
    effective_gain = gain
    if (is_monster_candidate(monster_score) and
            gain >= MONSTER_OVERRIDE_MIN_GAIN):
        effective_gain = max(gain, 2.01)   # force into Phase 4 block
        position['monster_override_active'] = True
    else:
        position['monster_override_active'] = False

    # ── MANDATORY OVERRIDES (all phases, no exceptions) ──────────────
    weekly_close = get_weekly_close(price_df, position['symbol'], as_of_date)
    if weekly_close < ma200:
        return 'FULL_EXIT', 'ma200_breach_backstop'
    if regime in ['Full Bear'] or indicators.get('crash_warning'):
        return 'FULL_EXIT', 'regime_bear'
    if regime == 'fast_crash_active':
        return 'REDUCE_50PCT', 'fast_crash_detector'
    if rs_rank < 20:
        return 'FULL_EXIT', 'rs_rank_total_collapse'   # hard exit — persistence does NOT apply below 20
    if get_sebi_fine_status(position['symbol']):
        return 'FULL_EXIT', 'sebi_fine'

    # ── PHASE 1: PROVE-IT (0% to 25% gain) ───────────────────────────
    if effective_gain < 0.25:
        stop_price = position['entry_price'] * (1 - PHASE1_STOP_PCT / 100)
        if current_price <= stop_price:
            return 'FULL_EXIT', 'phase1_stop'
        # v13: suppress time stop if ATR is compressing
        if position['holding_days'] >= TIME_STOP_DAYS and abs(gain) < TIME_STOP_MAX_GAIN:
            if not check_atr_compressing(position, indicators):
                return 'FULL_EXIT', 'time_stop'
            # else: ATR compressing — coiling base, suppress time stop
        return 'HOLD', None

    # ── PHASE 2: LET IT RUN (25% to 100% gain) ───────────────────────
    elif effective_gain < 1.00:
        # Exit 1: RS rank decay — v13 persistence filter
        # 4 consecutive weeks below floor required (not single-day)
        if check_rs_persistence(position, rs_rank, PHASE2_RS_FLOOR):
            return 'FULL_EXIT', 'phase2_rs_decay'

        # Exit 2: MA50 structurally declining
        ma50_21d = get_ma50_n_days_ago(price_df, position['symbol'], 21)
        if ma50 < ma50_21d:
            return 'FULL_EXIT', 'phase2_ma50_declining'

        # Exit 3: Volatility-adjusted 50DMA (v11)
        atr20    = indicators.get('atr20', current_price * 0.03)
        ma50_adj = ma50 - (ATR_MULT_50DMA * atr20)
        if current_price < ma50_adj:
            return 'FULL_EXIT', 'phase2_50dma_atr_break'

        # Exit 4: 21DMA logic — v12 volume + trend integrity layer
        if current_price < ma21:
            # NEW v12 Step A: classify pullback volume
            vol_class = classify_pullback_volume(position, current_price, indicators)

            if vol_class == 'LOW_VOLUME_HOLD_OVERRIDE':
                # Volume dry-up on pullback = healthy. Reset counter. Hold.
                position['ma21_below_count'] = 0
                # No exit action — this is the desired pullback pattern

            elif vol_class == 'HIGH_VOLUME_INSTANT_CONFIRM':
                # High volume breakdown = distribution confirmed immediately
                position['ma21_below_count'] = 0
                return 'REDUCE_25PCT', 'phase2_21dma_high_vol_instant'

            else:
                # AVERAGE_VOLUME_USE_COUNTER — standard path
                # NEW v12 Step B: check trend integrity before incrementing
                trend = check_trend_integrity(position['symbol'], price_df)

                if trend == 'INTACT':
                    # Higher highs and higher lows intact — suppress counter
                    # even on average volume. Pullback is constructive.
                    position['ma21_below_count'] = 0
                    # No exit action

                elif trend == 'BROKEN':
                    # Trend structure broken — confirm exit immediately
                    position['ma21_below_count'] = 0
                    return 'REDUCE_25PCT', 'phase2_21dma_trend_broken'

                else:
                    # NEUTRAL or UNKNOWN — increment counter as before
                    position['ma21_below_count'] = position.get('ma21_below_count', 0) + 1
                    vol_spike = (indicators.get('vol_ratio_20', 1.0) >= MA21_VOL_MULT)
                    if position['ma21_below_count'] >= MA21_CONFIRM_DAYS or vol_spike:
                        position['ma21_below_count'] = 0
                        return 'REDUCE_25PCT', 'phase2_21dma_confirmed'
        else:
            position['ma21_below_count'] = 0

        # Exit 5: Loose 20% trailing stop from 10-week high
        trail_stop = recent_10w_high * (1 - PHASE2_TRAIL_PCT / 100)
        if current_price <= trail_stop:
            return 'FULL_EXIT', 'phase2_trailing_stop'

        return 'HOLD', None

    # ── PHASE 3: WORKING COMPOUNDER (100% to 200% gain) ──────────────
    elif effective_gain < 2.00:
        # Exit 1: RS rank decay — v13 persistence filter (4 consecutive weeks)
        if check_rs_persistence(position, rs_rank, PHASE3_RS_FLOOR):
            return 'FULL_EXIT', 'phase3_rs_persistence'

        # Exit 2: MA50 declining
        ma50_21d = get_ma50_n_days_ago(price_df, position['symbol'], 21)
        if ma50 < ma50_21d:
            return 'FULL_EXIT', 'phase3_ma50_declining'

        # Exit 3: Volatility-adjusted 50DMA (v11)
        atr20    = indicators.get('atr20', current_price * 0.03)
        ma50_adj = ma50 - (ATR_MULT_50DMA * atr20)
        if current_price < ma50_adj:
            return 'FULL_EXIT', 'phase3_50dma_atr_break'

        # Exit 4: 21DMA logic — v12 volume + trend integrity layer (same as Phase 2)
        if current_price < ma21:
            vol_class = classify_pullback_volume(position, current_price, indicators)

            if vol_class == 'LOW_VOLUME_HOLD_OVERRIDE':
                position['ma21_below_count'] = 0
                # Hold — volume dry-up on pullback is constructive

            elif vol_class == 'HIGH_VOLUME_INSTANT_CONFIRM':
                position['ma21_below_count'] = 0
                return 'REDUCE_25PCT', 'phase3_21dma_high_vol_instant'

            else:
                trend = check_trend_integrity(position['symbol'], price_df)

                if trend == 'INTACT':
                    position['ma21_below_count'] = 0
                    # Hold — trend structure intact, suppress counter

                elif trend == 'BROKEN':
                    position['ma21_below_count'] = 0
                    return 'REDUCE_25PCT', 'phase3_21dma_trend_broken'

                else:
                    position['ma21_below_count'] = position.get('ma21_below_count', 0) + 1
                    vol_spike = (indicators.get('vol_ratio_20', 1.0) >= MA21_VOL_MULT)
                    if position['ma21_below_count'] >= MA21_CONFIRM_DAYS or vol_spike:
                        position['ma21_below_count'] = 0
                        return 'REDUCE_25PCT', 'phase3_21dma_confirmed'
        else:
            position['ma21_below_count'] = 0

        # Exit 5: 15% trailing stop from 10-week high
        trail_stop = recent_10w_high * (1 - PHASE3_TRAIL_PCT / 100)
        if current_price <= trail_stop:
            return 'FULL_EXIT', 'phase3_trailing_stop'

        # Exit 6: Climax run — SELL 50% (v11)
        if check_climax_run(position, price_df, CLIMAX_MIN_PRIOR_GAIN):
            return 'PARTIAL_EXIT_50PCT', 'phase3_climax_run'

        return 'HOLD', None

    # ── PHASE 4: MONSTER RUN (200%+ gain, or monster override) ───────
    # Force Motors territory. Tanla territory.
    # Bessembinder 2018: this is where the 4% of stocks that drive all
    # market wealth are held. Loose exits here are not a bug — they are
    # the primary source of alpha. Do not tighten Phase 4.
    else:
        # Staged partial exits at new ATHs
        all_time_high = price_df[position['symbol']]['adj_close'].max()
        is_new_ath    = current_price >= all_time_high * 0.99

        if is_new_ath and not position.get('phase4_exit1_done'):
            return 'PARTIAL_EXIT_25PCT', 'phase4_first_ath'
        if is_new_ath and not position.get('phase4_exit2_done'):
            return 'PARTIAL_EXIT_25PCT', 'phase4_second_ath'

        # PRIMARY exit: 10-week MA breach
        ma10w = get_10_week_ma(price_df, position['symbol'])
        if not np.isnan(ma10w) and current_price < ma10w:
            return 'EXIT_REMAINING_CORE', 'phase4_10week_ma_breach'

        # SECONDARY: 12% trail as backstop
        trail_stop = recent_10w_high * (1 - PHASE4_TRAIL_PCT / 100)
        if current_price <= trail_stop:
            return 'EXIT_REMAINING_CORE', 'phase4_core_trailing'

        # RS rank decay — persistence filter applies here too (4 weeks)
        if check_rs_persistence(position, rs_rank, PHASE2_RS_FLOOR):
            return 'EXIT_REMAINING_CORE', 'phase4_rs_persistence'

        # Climax run in Phase 4 — sell 50% of remaining
        if check_climax_run(position, price_df, CLIMAX_MIN_PRIOR_GAIN):
            return 'PARTIAL_EXIT_50PCT', 'phase4_climax_run'

        return 'HOLD', None
```

**Exit Phase Summary (v13)**

| Phase | Gain | Primary Exits | v12/v13 21DMA Layer | Monster Run |
|---|---|---|---|---|
| 1 | 0–25% | Fixed 8% stop from entry | N/A | Time stop suppressed if ATR compressing (v13) |
| 2 | 25–100% | RS persistence 4wks + 50DMA-1.5ATR | Low vol → hold override; High vol → instant confirm; Trend intact → suppress; Trend broken → confirm | 20% trail from 10W high |
| 3 | 100–200% | RS persistence 4wks + 50DMA-1.5ATR | Same as Phase 2 | 15% trail. Climax = sell 50% |
| 4 | 200%+ OR monster override (gain-gated ≥40%) | 10-week MA breach (primary) | Not applied in Phase 4 | ATH partial 25%+25% crystallised |
| Override | All | MA200 weekly / Bear / fast crash / RS<20 | SEBI fine | Full exit, no exceptions |

**Exit reason codes (v13):**
`phase1_stop` / `phase2_rs_persistence` / `phase2_ma50` / `phase2_50dma_atr_break` / `phase2_21dma_high_vol_instant` / `phase2_21dma_trend_broken` / `phase2_21dma_confirmed` / `phase2_trailing` / `phase3_rs_persistence` / `phase3_50dma_atr_break` / `phase3_21dma_high_vol_instant` / `phase3_21dma_trend_broken` / `phase3_21dma_confirmed` / `phase3_trailing` / `phase3_climax` / `phase4_first_ath` / `phase4_second_ath` / `phase4_10week_ma_breach` / `phase4_core_trailing` / `phase4_rs_persistence` / `phase4_climax` / `time_stop` / `time_stop_suppressed_atr` / `ma200_breach_backstop` / `regime_bear` / `fast_crash_detector` / `fast_crash_partial` / `rs_collapse` / `sebi_fine` / `large_cap` / `rebalance` / `manual` / `monster_override_active`

**Plant disaster event rule:** Confirmed one-time operational event (fire/flood/equipment failure): if MA200 holds on weekly close = maintain position. If MA200 breaches = standard mandatory exit applies.

---

### UC-10: Backtesting — 16 Tests Before Any Live Trading

**CRITICAL FIRST STEP:**
```python
# Set this BEFORE writing any backtest code
BACKTEST_END = '2022-12-31'  # 2023–2024 LOCKED as true OOS
# Cannot be done retroactively after seeing the data
```

**Execution rules (non-negotiable for all 16 tests):**

| Parameter | Value |
|---|---|
| Entry price | Next day open — NEVER same-day close |
| Slippage | +0.5% entry, -0.5% exit |
| Brokerage | 0.03% per side |
| STT | 0.1% on sell side |
| Exchange charges | 0.05% per side |
| Market impact | 0.1–0.3% depending on stock liquidity |
| Total round trip | Low 0.4% / mid 0.6% / high 0.8% |
| Position sizing | Fixed fractional 2% risk per trade |
| Circuit filter | Skip entry if stock hit upper circuit on signal day |
| Fundamentals | `reporting_date <= backtest_date` — zero look-ahead bias |
| Universe | Include ALL delisted stocks — survivorship bias prevention |
| Parameters | Only 10 free parameters — all others locked |
| Trial tracking | Log every trial — compute Deflated Sharpe Ratio at end |
| OOS holdout | 2023–2024 locked — never touched until Test 14 |

**Test 1 — Momentum Factor Weights**

Variants 1A through 1F (3m alone / 6m alone / 12-1 alone / equal / default 40-35-25 / default + vol scaling).

Fix P3 additions: pairwise Pearson correlation between factors; ANOVA/t-test for combined vs single-best (p < 0.10 required); RS rank correlation with composite score (if > 0.85, RS rank is redundant — remove).

Gate: Best variant beats Nifty 50 Sharpe by 0.3+. Combined signal must be statistically superior to single-best factor.

**Test 2 — Market Cap Band**

Variants 2A through 2F. Gate: Chosen band beats baseline Sharpe AND max drawdown.

**Test 3 — Regime Filter**

Variants 3A through 3D. Fix P10 India-specific threshold grid search required. Gate: Regime cuts max drawdown 30%+. Regime accuracy > 60% on predicting next-month direction. If fails: system is not viable — do not proceed.

**Test 4 — Trend Template**

Variants 4A through 4D. Gate: Improves win rate 5%+ OR Sharpe 0.2+. If fails: remove template entirely.

**Test 5 — Fundamental Approach**

Variants 5A through 5E. Gate: 5D must beat 5B on OOS Sharpe. Follow the data — do not defend the rules.

**Test 6 — VCP Win Rate**

Variants 6A through 6D. Gate: VCP win rate > 45%, avg win >= 2x avg loss, better than random entry. If fails: remove VCP entirely.

**Test 7 — Exit Rules**

**Test 7 — Exit Rules**

Variants 7A through 7F. Fix P4: 7D Calmar must beat 7A by ≥15% to justify complexity. Fix P12: post-time-stop return analysis. Boundary rule: if winning parameter at edge of tested range, extend and retest.

**Test 7G — Full 4-phase framework vs simplest trailing stop (already specified)**

Compare 7D (full 4-phase) directly against 7A (fixed 8% stop only) on OOS Calmar ratio. If 7D Calmar not at least 15% better than 7A: simplify to 7A.

**Test 7H — Correlation-adjusted sizing validation (NEW v14)**

Purpose: explicitly validate that `calculate_correlation_adjusted_size()` adds OOS Calmar ratio without unacceptably reducing signal frequency.

```
7H-A: Full system — NO correlation adjustment (baseline)
      Standard 2% risk rule + beta adjustment + float adjustment only
      All positions sized at full calculated size regardless of correlation

7H-B: Full system — WITH correlation adjustment (v14 spec)
      Additional Adjustment 3: corr > 0.70 = 25% reduction,
                                corr > 0.85 = 50% reduction
      All other rules identical to 7H-A
```

Metrics to compute for both variants:
- OOS Calmar ratio (CAGR / max drawdown) — primary gate
- Max drawdown during correlated market selloffs (Oct–Nov 2021, 2022 bear)
- Number of signals where correlation adjustment fired
- Signal frequency (positions entered per year) — must not drop > 10%
- Average position size (positions should be smaller but more frequent is fine)

**Gate:** 7H-B OOS Calmar must be >= 7H-A OOS Calmar.
Correlation adjustment must not hurt Calmar — it should improve or maintain it.

**Secondary gate:** Max drawdown in 7H-B must be <= 7H-A max drawdown.
The primary purpose of correlation sizing is drawdown reduction, not return improvement.

**If 7H-B fails primary gate (Calmar worse):**
→ Correlation adjustment is hurting returns by over-reducing position sizes.
→ Raise `CORR_HIGH_THRESHOLD` to 0.90 and re-test before removing entirely.
→ If still fails at 0.90: remove correlation adjustment, keep only beta + float adjustments.

**If signal frequency drops > 10%:**
→ Correlation thresholds may be too aggressive for NSE mid-cap sector clustering.
→ NSE mid-caps in the same sector naturally correlate 0.65–0.80 during normal markets.
→ If firing too often: raise `CORR_MED_THRESHOLD` to 0.75 and re-test.

**Expected result:** 7H-B should show modestly lower drawdown (−3 to −8 percentage points on max drawdown) with minimal CAGR impact (< −1%). This is the correct tradeoff — correlation sizing is a risk tool, not an alpha tool.

**Test 8 — Rebalancing Frequency**

Variants 8A through 8D. Gate: Best net-of-cost Calmar ratio.

**Test 9 — Volume and Institutional Signal Validation**

Part A (9A–9E): OBV vs delivery. Gate A: 9D beats 9A on OOS Sharpe. Gate B: 9D beats 9E.
Part B (9F–9H): Smart institutional flow. Gate (updated): 9H must beat 9F by statistically significant margin (p < 0.10). Directional improvement alone is NOT sufficient.

**Test 10 — Full Integrated System**

14 required metrics. 6 hard gates — ALL must pass: positive expectancy, Sharpe > 0.8, max drawdown < 25%, CAGR > 15% net of costs, outperforms Nifty 50 by 5%+ CAGR, positive returns in at least 3 of 4 regime types.

**Test 11 — Null Hypothesis Shuffle Test**

1,000 shuffles. Gate: p-value < 0.05 vs shuffled distribution.

**Test 12 — Deflated Sharpe Ratio**

Gate: DSR > 0.95 × IS Sharpe.

**Test 13 — Probability of Backtest Overfitting**

CSCV method, 8 sub-periods. Gate: PBO < 30%.

**Test 14 — True OOS Reveal**

2023–2024 data revealed. ZERO parameter changes from Test 10. If parameters need changing: system is overfit, start over.

**Test 15 — Transaction Cost Sensitivity**

5 scenarios (0.4% / 0.6% / 0.8% / 1.0% / 1.5% round trip). Gate: Positive expectancy must survive 15A through 15D. If fails at 15D: raise `MARKET_CAP_MIN_CR` until positive expectancy survives 1.0%.

**Test 16 — Capacity Test**

5 AUM levels (₹25cr / ₹50cr / ₹100cr / ₹200cr / ₹500cr). Gate: Identify AUM level at which Sharpe drops below 0.6. Report — do not pre-claim any specific capacity.

---

### UC-11: Walk-Forward Validation

**Expanding Window (Primary)**

| Fold | Train | Test | Focus |
|---|---|---|---|
| 1 | 2015–2018 | 2019–2020 | COVID crash |
| 2 | 2015–2019 | 2020–2021 | V-recovery bull |
| 3 | 2015–2020 | 2021–2022 | Inflation bear |
| 4 | 2015–2021 | 2022 | Final IS year |

Gate: OOS Sharpe >= 70% of IS Sharpe in ALL 4 folds.

**Rolling Window (Secondary)**

| Fold | Train | Test |
|---|---|---|
| 5 | 2015–2018 | 2019–2020 |
| 6 | 2017–2020 | 2021–2022 |
| 7 | 2019–2022 | 2023 (partial OOS) |

Gate: Rolling-window OOS Sharpe not materially worse than expanding-window (within 15 percentage points).

**Adversarial Fold (NEW v14 — Fold 8)**

| Fold | Train | Test | Purpose |
|---|---|---|---|
| 8 | 2015–2016 + 2018 + 2022 (non-bull years only) | 2019 (bull recovery) | Detect bull-market overfit |

**Fold 8 construction:**
```python
# Training set: only non-bull calendar years
# 2015-2016: Nifty sideways/weak, midcap underperformance
# 2018:      Nifty correction, NBFC crisis, midcap bear (-25%)
# 2022:      Rate hike bear, FII selloff, inflation regime
# Deliberately excludes: 2017 (strong bull), 2019-2021 (V-recovery + bull)

# Test set: 2019 bull recovery
# Why 2019: system trained only on bear/weak years must still perform
#           when markets transition to bull. Tests regime detection quality.

FOLD8_TRAIN_YEARS = [2015, 2016, 2018, 2022]  # non-contiguous — handled in backtest
FOLD8_TEST_YEAR   = 2019
```

**Gate:** OOS Sharpe on Fold 8 >= 50% of Folds 1–4 average Sharpe.
Lower bar (50% vs 70%) because training data is adversarially selected — the system has never seen a sustained bull market in its training set.

**Interpretation:**
- **Pass:** System parameters are not regime-biased. The regime engine correctly identifies bull conditions even when calibrated on bear years.
- **Fail (OOS Sharpe < 50% of average):** Critical finding — parameters are overfit to bull-heavy training. Most likely cause: regime thresholds (S3 breadth, S5 extension) tuned too loosely, causing delayed bull entry. Re-run Test 3 with tighter regime calibration before proceeding.
- **Fail (negative OOS Sharpe):** System cannot trade a bull market it has never seen in training. Fundamental architecture problem — escalate to full design review.

**Implementation note:** Non-contiguous training years require careful data handling. Build training set by filtering `backtest_results` rows to `FOLD8_TRAIN_YEARS` only. Ensure no data leakage from 2017, 2019–2021 which are excluded from training. Walk-forward engine must support non-contiguous year selection — add `train_year_filter` parameter to backtest runner.

---

### UC-12: Paper Trading (6 Months Minimum)

Duration: 120+ trading days minimum. Must experience at least one full regime transition.

**Daily tracking:** Every signal generated, would-have-been P&L at next-day open, earnings flag accuracy, max entry rule triggers, regime calls vs actual market behaviour, exit cascade signals.

**Weekly chart review:** VCP base visual quality, OBV slope during base, earnings dates, exit signal alignment.

**Go-live gates — all must pass:**
- [ ] 95%+ pipeline success rate across 120+ days
- [ ] Live win rate within 10% of backtest win rate
- [ ] 15+ Tier 1 signals generated and manually reviewed
- [ ] Regime calls match market view 80%+ of days
- [ ] Earnings safety flag correctly identified 5+ situations
- [ ] Max entry 3% rule triggered 3+ times
- [ ] Exit cascade fired at least once (E1 or E2 or E3)
- [ ] Owner personally confident in every signal after chart review
- [ ] Live vs paper P&L correlation > 0.90

---

### UC-13: Go-Live Decision Checklist (25 Gates)

Nothing gets real money until ALL 25 gates are checked. No exceptions.

**Data Integrity Gates (7)**
- [ ] adj_close verified on 10 known split/bonus events
- [ ] reporting_date verified — zero look-ahead on 20 random fundamental checks
- [ ] Crash indicator verified — fires April 2020 condition
- [ ] ADV decline rule verified — open positions NOT auto-exited when ADV drops (Fix P2)
- [ ] VCP unit test passed — detection rate ≥80%, false positive rate ≤10% (Fix P9)
- [ ] Sector normalisation verified — revenue/OPM scores use sector-relative calculation (Fix P11)
- [ ] **Sector rankings verified — `calculate_sector_rankings()` produces stable daily output, top-3 and bottom-3 flags match manual inspection of 5 known sector rotations (NEW v14)**

**Component Backtest Gates (10)**
- [ ] Test 1: Optimal weights found → settings.py updated
- [ ] Test 2: Optimal market cap band → settings.py updated
- [ ] Test 3: Regime cuts drawdown 30%+ AND crash fires April 2020
- [ ] Test 4: Trend template adds value (or removed with evidence)
- [ ] Test 5: Bonus scores beat hard filters on OOS Sharpe — **verify SUE proxy bonus (Bonus 9) adds incremental OOS alpha; if not, set PEAD_ENABLED = False (v14)**
- [ ] Test 6: VCP win rate > 45%, avg win >= 2x avg loss
- [ ] Test 7: Best exit rule found → settings.py updated
- [ ] Test 8: Best rebalancing frequency → settings.py updated — **verify monthly_rebalance() logic executes correctly on last trading day of month (NEW v14)**
- [ ] Test 9: OBV beats delivery; smart institutional beats blind FII
- [ ] Test 10: Full system — all 6 hard gates passed

**Institutional Grade Statistical Gates (Tests 11–16)**
- [ ] Test 11: Null hypothesis p-value < 0.05
- [ ] Test 12: Deflated Sharpe Ratio > 0.95 × IS Sharpe
- [ ] Test 13: PBO < 30% via CSCV method
- [ ] Test 14: True OOS 2023–2024 passes with ZERO parameter changes
- [ ] Test 15: Positive expectancy at 15A–15D (survives up to 1.0% round-trip costs)
- [ ] Test 16: Capacity ceiling identified — maximum AUM reported (not pre-claimed)

**Walk-Forward Gates**
- [ ] Expanding-window: OOS Sharpe >= 70% IS in all 4 folds
- [ ] Rolling-window: not materially worse than expanding
- [ ] **Adversarial Fold 8: OOS Sharpe >= 50% of Folds 1–4 average. If fails: re-run Test 3 regime calibration before proceeding (NEW v14)**

**v14 Specific Implementation Gates (3)**
- [ ] **`calculate_correlation_adjusted_size()` verified — at least 3 manual test cases: (a) uncorrelated stocks = no adjustment, (b) corr 0.75 = 25% reduction, (c) corr 0.88 = 50% reduction (NEW v14)**
- [ ] **`calculate_sue_proxy_bonus()` verified — SUE proxy fires correctly at eps_growth_yoy > 50% (+10), > 25% (+6), < -20% (-8). Expires after 60 trading days from reporting_date. `PEAD_ENABLED = True` confirmed in settings.py (v14)**
- [ ] **`run_turnaround_watch_scan()` verified — fires correctly on at least 1 known historical turnaround stock. Turnaround Watch panel displays correctly with MONITORING ONLY warning. Hard block suppression confirmed (pledge/SEBI/pivot stocks do not appear on panel). (NEW v16)**

**Paper Trading Gates**
- [ ] All 8 paper trading items checked (UC-12)
- [ ] 120+ trading days completed
- [ ] Live vs paper P&L correlation > 0.90

**Live Deployment Sequence**

| Period | Capital |
|---|---|
| Month 1–3 | 10% of intended capital (NOT 25%) |
| Month 4–6 | 25% only if live win rate within 10% of backtest AND correlation > 0.90 |
| Month 7+ | Full capital only after 6 months live validation |

---

### UC-14: Daily Live Pipeline

| Step | Action | Time |
|---|---|---|
| 1 | Holiday calendar check — if holiday, log skip and exit | 10s |
| 2 | Download NSE bhav copy (EQ series only) | 3 min |
| 3 | Download delivery bhav copy | 1 min |
| 4 | Download FII/DII aggregate data | 1 min |
| 5 | Download bulk/block deals | 1 min |
| 6 | Check NSE FII breach/caution list | 1 min |
| 7 | Check corporate actions → apply adj_factor if new | 2 min |
| 8 | Run data validation gate (UC-01 Step 7). **Also check `data_quality_alerts` table for any CRITICAL alerts unresolved > 24h — if found, halt pipeline and WhatsApp alert to developer before proceeding. WARNING-level alerts: continue pipeline, suppress affected symbol only.** | 2 min |
| 9 | Update price_data (raw close + adj_close) | 2 min |
| 10 | Calculate all indicators + OBV + ATR14 (UC-02) — store `atr_at_entry` on new positions | 5 min |
| 11 | Calculate 6-signal regime + crash indicator (UC-03) | 2 min |
| 11a | Run fast crash detector `check_fast_crash()` (UC-03D — v13). If fires: execute `apply_fast_crash_response()` at next open | 30s |
| 12 | Check exit cascade E2–E4 at portfolio level (UC-03B) | 2 min |
| **12a** | **Run `run_turnaround_watch_scan()` (UC-04 Step 0B — NEW v16). Scans all tracked symbols for EPS turnaround. Updates turnaround_watch table. WhatsApp alert to Mohit for any new entries. Hard blocks still apply — monitoring only.** | **1 min** |
| **13a** | **Calculate sector rankings `calculate_sector_rankings()` (UC-04 Step 0 — NEW v14). Store in `sector_rankings` table. Output feeds steps 14–15.** | **1 min** |
| 13 | Run 8 hard block filters on universe (UC-04 Step 1) | 2 min |
| 14 | Rank universe: momentum composite + vol scaling using sector ranks from Step 13a (UC-04 Step 2) | 3 min |
| 15 | Calculate fundamental bonus/penalty scores including PEAD earnings surprise bonus (UC-04 Step 3 — v14) | 2 min |
| 16 | Calculate smart institutional flow signals (UC-04 Step 4) | 1 min |
| 17 | Calculate monster scores for all eligible stocks including sector outperformance criterion (UC-04 Step 5) | 2 min |
| 18 | Apply 8-condition trend template (UC-05) | 2 min |
| 19 | Detect VCP/tight base + OBV slope (UC-06) | 4 min |
| 20 | Confirm/fail yesterday's Pending signals (UC-06) | 1 min |
| 21 | Check earnings dates + flag <10 days (UC-08) | 1 min |
| 22 | Calculate position sizes with correlation-aware adjustment + regime-dependent heat + sector check (UC-07 — v14) | 2 min |
| 23 | Generate watchlist + monster candidates panel (UC-08) | 1 min |
| 24 | Check phase-based exit signals for all open positions (UC-09 v13) | 2 min |
| 25 | Check RS persistence counter — increment weekly on Fridays only; reset immediately if RS recovers (v13) | 1 min |
| 26 | Check E1 climax run on Phase 3/4 positions (UC-03B) | 1 min |
| 27 | Check volume direction + trend integrity on all open positions (v12) | 1 min |
| 28 | Check ATR compression on all Phase 1 time-stop candidates — suppress if compressing (v13) | 30s |
| 29 | Check monster override activation status — update `monster_override_active` flag on all positions (v13) | 30s |
| 30 | Check large-cap graduation on all holdings | 30s |
| **30a** | **If last trading day of month: run `monthly_rebalance()` (UC-08B — NEW v14). Queue all actions for next-day open execution.** | **2 min** |
| 31 | Update performance tracker (UC-15) | 1 min |
| **31a** | **Generate daily ops report (UC-18) — archive + WhatsApp delivery** | **1 min** |
| **31b** | **If Friday: generate weekly review report (UC-19) — archive + email delivery** | **2 min** |
| **31c** | **If last trading day of month: generate monthly client report (UC-20) [PHASE 2]** | **3 min** |
| **31d** | **If Friday: run strategy decay check (UC-39) [PHASE 3]** | **30s** |
| **31e** | **If Friday: update signal quality trends (UC-40) [PHASE 3]** | **1 min** |
| 32 | Refresh Streamlit dashboard | 1 min |
| 33 | Send WhatsApp + email alerts for Tier 1 signals + manual review flags | 2 min |
| **Total** | | **~60 min** |

Dashboard live by 5:00 PM IST.

---

### UC-15: Performance Tracking

| Field | Description |
|---|---|
| user_id | Portfolio owner |
| symbol | NSE ticker |
| entry_date | Date of actual entry |
| entry_price | System-suggested price |
| actual_fill | Actual price paid (slippage measurement) |
| exit_date | Date of exit |
| exit_price | Actual exit price |
| exit_reason | One of exit reason codes (v13 expanded list) |
| pnl_pct | Percentage P&L |
| pnl_inr | Rupee P&L |
| max_gain_pct | Maximum favourable excursion (MFE) |
| max_loss_pct | Maximum adverse excursion (MAE) |
| holding_days | Days held |
| pattern_type | VCP / TightBase / Breakout |
| regime_at_entry | Regime when entered |
| vol_scalar | Volatility scalar applied |
| obv_bonus | OBV bonus at entry (0 or 5) |
| earnings_flagged | Was earnings warning shown at entry? |
| days_to_earnings | Days to results at entry date |
| **monster_score_at_entry** | **Monster score at time of entry (NEW v12)** |
| **was_monster_override** | **Was Phase 4 applied via monster override? (NEW v12)** |

**Monthly review questions:**
1. Live win rate vs backtest win rate — within 10%?
2. Live slippage vs 0.5% assumption — are we overpaying?
3. Which pattern type has best live win rate?
4. Are earnings-flagged signals underperforming unflagged?
5. Max entry 3% rule — triggered how often? Too restrictive?
6. OBV bonus stocks — outperforming non-OBV stocks?
7. Exit cascade — did E1/E2/E3 fire before MA200 breach?
8. Monster candidates — are high monster-score stocks outperforming the median?
9. Were any low-volume hold overrides correct? (did the stock continue higher?)
10. Were any high-volume instant confirms correct? (did the stock continue lower?)
11. RS persistence filter — how many positions were held past the old single-week exit that would have triggered? Did those holds produce better or worse outcomes?
12. ATR compression suppression — how many time stops were suppressed? Did those positions subsequently break out as expected?
13. Fast crash detector — did it fire before the regime engine transitioned? How much drawdown was avoided?
14. Monster override gain gate — at what gain level did override activate? Were positions with gain < 40% that scored >= 80 later justified?
15. **SUE proxy bonus — are stocks with active SUE drift window (eps_growth_yoy > 25%) outperforming stocks without it over the 60-day window? Validates Bernard & Thomas 1989 + Chan et al. 1996 on NSE mid-caps using YoY EPS growth. (v14)**
16. **Sector rankings — is the top-3 sector bonus (+10) producing measurable alpha vs stocks outside top 3? Compare average return by sector rank bucket. (NEW v14)**
17. **Correlation adjustment — how many entries were sized down due to correlation? Did those reduced-size positions perform better or worse than full-size entries? (NEW v14)**
18. **Monthly rebalance — how many trim-oversize actions fired? How many Tier 1 slots were filled during rebalance vs intra-month? Are rebalance-filled entries performing comparably to intra-month entries? (NEW v14)**

---

### UC-16: Subscription Tiers (Phase 2 — After SEBI RA Registration)

**IMPORTANT: Do not charge for signals until SEBI Research Analyst registration is active. Run free beta with trusted clients during paper trading phase.**

| Tier | Monthly | Annual | Target User |
|---|---|---|---|
| Starter | ₹2,999 | ₹29,990 | Active retail, 1–5 positions/month |
| Pro | ₹9,999 | ₹99,990 | Serious trader, 5–15 positions/month |
| Institutional | ₹30,000+ | ₹3,00,000+ | HNI, family office, fund manager |

| Feature | Starter | Pro | Institutional |
|---|---|---|---|
| Regime indicator + crash warning | ✓ | ✓ | ✓ |
| Top 10 watchlist (names only) | ✓ | ✓ | ✓ |
| Sector rotation rankings | ✗ | ✓ | ✓ |
| Full Tier 1 signals (entry/stop/size) | ✗ | ✓ | ✓ |
| Full Tier 2 + Tier 3 signals | ✗ | ✓ | ✓ |
| OBV divergence per signal | ✗ | ✓ | ✓ |
| Earnings safety flag | ✗ | ✓ | ✓ |
| Composite score per signal | ✗ | ✓ | ✓ |
| Smart institutional flow signal | ✗ | ✓ | ✓ |
| **Monster candidates panel (NEW v12)** | **✗** | **✓** | **✓** |
| **Monster score per signal (NEW v12)** | **✗** | **✓** | **✓** |
| WhatsApp + email alerts | ✗ | ✓ | ✓ |
| Regime change alerts | ✗ | ✓ | ✓ |
| Historical signal archive | ✗ | ✓ | ✓ |
| Backtest results summary | ✗ | ✓ | ✓ |
| Full REST API access | ✗ | ✗ | ✓ |
| Webhook signal delivery | ✗ | ✗ | ✓ |
| Custom position size limits | ✗ | ✗ | ✓ |
| Portfolio P&L tracking | ✗ | ✗ | ✓ |
| Monthly strategy review call | ✗ | ✗ | ✓ |

---

### UC-17: Dashboard and Client Interface (Specification Pending)

Full dashboard UI specification is a separate document to be written after backtest completion and paper trading begins.

**Minimum viable dashboard (Streamlit — Phase 1):**
- Current regime score with all 6 signal breakdown
- Today's watchlist with tier, score, entry zone, stop, size
- Monster candidates panel
- Open positions tracker with current P&L, exit alerts, and volume pullback status
- Earnings safety warnings for all open positions

**Client login and subscription tier gating:** Added after SEBI RA registration is filed.

**Full React frontend specification:** Written after 6 months Streamlit validation.

---

## REPORTING LAYER — UC-18 through UC-22

---

### UC-18: Daily Operations Report `[PHASE 1 — activate immediately]`

**Trigger:** Auto-runs at 5:00 PM IST every trading day after pipeline step 33 completes.
**Output:** Plain text + Markdown. Archived to `reports/daily/YYYY-MM-DD.md`. Delivered via WhatsApp and email to Mohit.
**Purpose:** Confirm pipeline is healthy, know current risk exposure, catch any alerts before next morning.

```python
def generate_daily_ops_report(db, as_of_date, open_positions,
                               regime, pipeline_log):
    """
    Daily operations report — auto-generated 5:00 PM IST.
    PHASE 1: active from paper trading day 1.
    """
    report = []
    report.append(f"# UniPro AI — Daily Operations Report")
    report.append(f"**Date:** {as_of_date} | **Regime:** {regime['regime_name']}")
    report.append(f"**Pipeline status:** {get_pipeline_status(pipeline_log, as_of_date)}")
    report.append("")

    # Section 1: Regime
    report.append("## Regime")
    report.append(f"Current: **{regime['regime_name']}** (score: {regime['regime_score']}/6)")
    report.append(f"Days at current level: {get_regime_days(db, regime['regime_name'], as_of_date)}")
    report.append(f"Fast crash status: {'⚠️ ACTIVE' if regime.get('fast_crash_active') else '✓ Clear'}")
    report.append(f"Crash indicator: {'⚠️ WARNING' if regime.get('crash_warning') else '✓ Clear'}")

    # Section 2: Portfolio risk
    portfolio_value = get_portfolio_value(db)
    current_heat    = calculate_current_heat(open_positions, portfolio_value)
    max_heat        = get_max_heat(regime['regime_name'])
    report.append("")
    report.append("## Portfolio Risk")
    report.append(f"Open positions: {len(open_positions)}")
    report.append(f"Portfolio heat: {current_heat:.1f}% / {max_heat:.1f}% limit")
    report.append(f"Largest position: {get_largest_position(open_positions, portfolio_value)}")
    report.append(f"Sector concentration: {get_top_sector_concentration(open_positions, portfolio_value)}")

    # Section 3: Positions near key levels
    report.append("")
    report.append("## Alerts")
    alerts = get_position_alerts(db, open_positions, as_of_date)
    if alerts:
        for alert in alerts:
            report.append(f"- {alert}")
    else:
        report.append("- No alerts today")

    # Section 4: Signals today
    tier1_today = get_signals_by_date_tier(db, as_of_date, tier=1)
    report.append("")
    report.append(f"## Signals Today")
    report.append(f"Tier 1: {len(tier1_today)} | Tier 2: {get_signal_count(db, as_of_date, 2)} | Tier 3: {get_signal_count(db, as_of_date, 3)}")

    # Section 5: Data quality
    report.append("")
    report.append("## Data Quality")
    dq_issues = get_data_quality_issues(pipeline_log, as_of_date)
    if dq_issues:
        for issue in dq_issues:
            report.append(f"⚠️ {issue}")
    else:
        report.append("✓ All data checks passed")

    # Section 6: Next day prep
    earnings_tomorrow = get_earnings_next_n_days(db, as_of_date, days=3)
    report.append("")
    report.append("## Next 3 Days — Earnings Watch")
    for e in earnings_tomorrow:
        report.append(f"- {e['symbol']}: results expected {e['expected_result_date']}")

    return "\n".join(report)
```

**Delivery:**
```python
def deliver_daily_report(report_text, as_of_date):
    # Archive
    save_to_file(f"reports/daily/{as_of_date}.md", report_text)
    store_in_db('report_archive', as_of_date, 'daily', report_text)
    # Deliver
    send_whatsapp(MOHIT_PHONE, report_text[:500] + "... [full report archived]")
    send_email(MOHIT_EMAIL, f"UniPro Daily Ops — {as_of_date}", report_text)
```

---

### UC-19: Weekly Review Report `[PHASE 1 — activate immediately]`

**Trigger:** Auto-runs every Friday at 5:30 PM IST after daily pipeline completes.
**Output:** Markdown + PDF. Archived to `reports/weekly/YYYY-WW.pdf`. Delivered to Mohit.
**Purpose:** Answer all 18 UC-15 review questions with live data. Full week in review.

```python
def generate_weekly_report(db, week_end_date):
    """
    Weekly review — every Friday 5:30 PM IST.
    Answers all 18 UC-15 monthly review questions on a weekly basis.
    PHASE 1: active from paper trading day 1.
    """
    week_start = week_end_date - timedelta(days=4)
    trades_this_week = get_trades_in_range(db, week_start, week_end_date)

    report = {}

    # Performance
    report['weekly_pnl_pct']    = calculate_period_pnl(db, week_start, week_end_date)
    report['ytd_pnl_pct']       = calculate_ytd_pnl(db, week_end_date)
    report['vs_nifty_this_week']= calculate_alpha_vs_nifty(db, week_start, week_end_date)

    # Signal quality
    report['signals_generated'] = get_signal_count_range(db, week_start, week_end_date)
    report['tier1_confirmed']   = get_confirmed_signals(db, week_start, week_end_date)
    report['tier1_failed']      = get_failed_signals(db, week_start, week_end_date)
    report['confirmation_rate'] = report['tier1_confirmed'] / max(report['signals_generated'], 1)

    # Win rate (rolling 90 days for statistical reliability)
    report['win_rate_90d']      = calculate_rolling_win_rate(db, week_end_date, days=90)
    report['backtest_win_rate'] = get_backtest_win_rate(db)
    report['win_rate_gap']      = report['win_rate_90d'] - report['backtest_win_rate']

    # Slippage
    report['avg_slippage_week'] = calculate_avg_slippage(db, week_start, week_end_date)

    # UC-15 questions 15–18 (v14 specific)
    report['sue_proxy_accuracy']= calculate_sue_signal_accuracy(db, week_end_date)
    report['sector_rank_accuracy']= calculate_sector_rank_accuracy(db, week_end_date)
    report['corr_adj_outcome']  = calculate_correlation_adj_outcomes(db, week_end_date)
    report['rebalance_actions'] = get_rebalance_actions_this_week(db, week_start, week_end_date)

    # Regime
    report['regime_changes']    = get_regime_changes_in_range(db, week_start, week_end_date)
    report['regime_accuracy']   = calculate_regime_accuracy(db, week_end_date, lookback_weeks=12)

    # Monster
    report['monster_candidates_new'] = get_new_monster_candidates(db, week_start, week_end_date)
    report['monster_outperformance'] = calculate_monster_outperformance(db, week_end_date, lookback_days=60)

    # Forward look
    report['earnings_next_week'] = get_earnings_next_n_days(db, week_end_date, days=7)
    report['sector_rankings_top3'] = get_top_sectors(db, week_end_date, n=3)
    report['sector_rankings_bot3'] = get_bottom_sectors(db, week_end_date, n=3)

    return format_weekly_report(report, week_end_date)
```

---

### UC-20: Monthly Client Report `[PHASE 2 — activate on SEBI RA registration]`

**Trigger:** Auto-runs on last trading day of month after `monthly_rebalance()` completes.
**Output:** Two PDFs per month — Internal (full data) and External (client-facing, SEBI-compliant).
**Delivery:** External PDF delivered to Pro and Institutional subscribers via email and client portal.

**External report structure (SEBI RA compliant):**
```
Header:
  UniPro AI Research — Monthly Strategy Report
  SEBI RA Registration: INH[number]
  Report Date: [date]
  Research Analyst: Mohit [surname]

1. Performance Summary
   MTD return (net of costs): X%
   YTD return: X%
   Since inception: X%
   vs Nifty 50 MTD: +/- X%
   vs Nifty Midcap 150 MTD: +/- X%
   Rolling 12-month Sharpe: X
   Rolling 12-month max drawdown: X%

2. Portfolio Snapshot
   Number of holdings: X
   Market regime at month end: [regime name]
   Top 5 holdings (name, sector, % of portfolio, gain since entry)
   Sector allocation: [table]

3. Activity This Month
   Positions entered: X (signal type breakdown)
   Positions exited: X (exit reason breakdown)
   Monthly rebalance actions: X

4. Strategy Commentary (1 paragraph — written by Mohit, not auto-generated)
   [placeholder — Mohit fills in before delivery]

5. Risk Metrics
   Portfolio heat at month end: X%
   Average holding period: X days
   Win rate MTD: X% (vs backtest X%)

6. Market Outlook (1 paragraph — written by Mohit)
   [placeholder]

Footer (SEBI mandatory):
   This research report is prepared by UniPro AI Research, a SEBI Registered
   Research Analyst (Registration No. INH[number]). Registration does not imply
   SEBI endorsement of performance. Past performance is not indicative of future
   results. Investors should assess their own risk tolerance before acting on
   this research. Full disclaimer available at uniproadvisory.com/disclaimer.
```

**Internal report adds:**
```
Full P&L attribution by signal type
Exit reason attribution
SUE proxy accuracy this month
Sector ranking accuracy this month
Correlation adjustment impact
Monster score accuracy
All 18 UC-15 review questions answered
Parameter stability check
Any strategy decay warning flags
```

---

### UC-21: Quarterly Attribution Report `[PHASE 3 — activate at go-live]`

**Trigger:** Auto-generates on last trading day of March, June, September, December.
**Output:** PDF. Internal only. Archived to `reports/quarterly/`.

**Contents:**
```python
QUARTERLY_REPORT_SECTIONS = {
    'performance': [
        'quarterly_return_gross',
        'quarterly_return_net',
        'benchmark_alpha_quarterly',
        'rolling_sharpe_12m',
        'rolling_calmar_12m',
        'max_drawdown_this_quarter',
        'max_drawdown_vs_backtest_distribution',
    ],
    'attribution': [
        'alpha_from_momentum_factor',        # momentum vs equal-weight universe
        'alpha_from_regime_timing',          # regime-on vs regime-off returns
        'alpha_from_vcp_detection',          # VCP entries vs non-VCP entries
        'alpha_from_fundamental_bonus',      # bonus-score stocks vs no-bonus stocks
        'alpha_from_monster_score',          # monster candidates vs non-candidates
        'alpha_from_sector_rotation',        # top-3 sector stocks vs others
        'alpha_from_sue_proxy',              # SUE bonus active stocks vs others
        'cost_drag',                         # slippage + brokerage + STT total
    ],
    'signal_validity': [
        'live_win_rate_vs_backtest',
        'live_avg_win_vs_backtest',
        'live_avg_loss_vs_backtest',
        'win_rate_trend_90d',                # is win rate improving or declining?
        'exit_reason_distribution',          # what is causing most exits?
        'phase_distribution',                # what phase are most exits in?
    ],
    'regime_analysis': [
        'regime_accuracy_this_quarter',
        'performance_by_regime',             # returns in each regime
        'crash_detector_events',             # how many times fired, how much drawdown saved
        'fast_crash_vs_regime_timing',       # which fires earlier?
    ],
    'strategy_decay': [
        'is_win_rate_within_2sd_of_backtest',
        'is_sharpe_within_acceptable_range',
        'parameter_stability_check',
        'decay_warning_active',              # True if degrading
    ],
}
```

---

### UC-22: Annual Strategy Review `[PHASE 5 — activate at AIF/PMS stage]`

**Trigger:** Manual initiation by Mohit on last trading day of December.
**Output:** Full audit document. Internal only. Requires Mohit's narrative sections.

**Structured data package auto-generated:**
```
Is momentum still working on NSE?
  - Compare last 12 months live Sharpe vs 2010-2022 backtest distribution
  - P-value: is live performance statistically consistent with backtest?
  - Any structural break in momentum factor on NSE?

Evidence base review:
  - List all 15 citations with notes on any updates published this year
  - Any contradicting research published? (search PubMed, SSRN for new papers)
  - Any of the 15 papers retracted or substantially revised?

Parameter review:
  - Current FREE parameter values vs backtest-optimal values
  - Have any parameters drifted to edge of their test range? (re-test required)
  - Proposed parameter updates (if any) with DSR calculation for each

Signal audit:
  - Which of the 9 bonus signals have statistically significant live alpha?
  - Which signals fire too rarely for statistical confidence (< 20 occurrences)?
  - Any signals consistently degrading performance? (remove or downweight)

Universe review:
  - NSE market cap distribution changes this year
  - Any new ASM/ESM patterns emerging in specific sectors?
  - Should MARKET_CAP_MIN_CR be updated?

Regulatory review:
  - SEBI rule changes this year affecting RA operations
  - SEBI circular updates affecting momentum advisory
  - RA licence renewal requirements and timeline
  - AIF/PMS threshold — are we approaching it?
```

---

## CLIENT MANAGEMENT LAYER — UC-23 through UC-26

---

### UC-23: Client Onboarding `[PHASE 2 — activate on SEBI RA registration]`

**Purpose:** Complete digital onboarding flow compliant with SEBI RA regulations. Every client must complete this before receiving any signals.

**Required documents (SEBI RA mandate):**
```
1. Risk Disclosure Document (RDD) — SEBI prescribed format
   Client must read and sign. Explains:
   - Research analyst is not a portfolio manager
   - Past performance does not guarantee future returns
   - Client is solely responsible for investment decisions
   - Conflicts of interest disclosure

2. Terms of Service Agreement
   - Subscription tier and pricing
   - Cancellation policy
   - Data usage and privacy
   - Intellectual property (signals are proprietary research)

3. Risk Profiling Questionnaire
   - Investment horizon
   - Risk tolerance (conservative/moderate/aggressive)
   - Investment experience
   - Financial capacity for losses
   Assign to: Tier 1 (conservative) → Starter only
              Tier 2 (moderate) → Starter + Pro
              Tier 3 (aggressive) → All tiers

4. KYC (PAN verification minimum for RA)
   - PAN card number
   - Name as per PAN
   - Mobile and email verification
   For AIF/PMS: full KYC per PMLA requirements
```

**Database additions:**
```sql
CREATE TABLE clients (
    client_id           VARCHAR(20) PRIMARY KEY,
    name                VARCHAR(100),
    email               VARCHAR(100) UNIQUE,
    phone               VARCHAR(15),
    pan                 VARCHAR(10),
    kyc_verified        BOOLEAN DEFAULT FALSE,
    kyc_date            DATE,
    risk_profile        VARCHAR(20),         -- conservative/moderate/aggressive
    subscription_tier   VARCHAR(20),
    subscription_start  DATE,
    subscription_end    DATE,
    rdd_signed          BOOLEAN DEFAULT FALSE,
    rdd_signed_date     DATE,
    tos_signed          BOOLEAN DEFAULT FALSE,
    tos_signed_date     DATE,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW(),
    -- SEBI audit fields
    onboarding_ip       VARCHAR(45),
    onboarding_device   VARCHAR(100)
);
```

---

### UC-24: Client Portal `[PHASE 4 — activate at SaaS launch]`

**Purpose:** Each subscriber logs in to see their tier's content. Tier-gated delivery.

**Portal panels by tier:**

| Panel | Starter | Pro | Institutional |
|---|---|---|---|
| Regime indicator + crash warning | ✓ | ✓ | ✓ |
| Top 10 watchlist (names only) | ✓ | ✓ | ✓ |
| Full Tier 1/2/3 signals with entry/stop/size | ✗ | ✓ | ✓ |
| Monster candidates panel | ✗ | ✓ | ✓ |
| Sector rotation rankings | ✗ | ✓ | ✓ |
| OBV divergence + SUE proxy indicator | ✗ | ✓ | ✓ |
| Historical signal archive | ✗ | ✓ | ✓ |
| Weekly report PDF download | ✗ | ✓ | ✓ |
| Monthly report PDF download | ✗ | ✓ | ✓ |
| Portfolio P&L tracker (personal trades) | ✗ | ✗ | ✓ |
| Full REST API access | ✗ | ✗ | ✓ |
| Webhook signal delivery | ✗ | ✗ | ✓ |
| Custom position size limits | ✗ | ✗ | ✓ |
| Monthly strategy review call | ✗ | ✗ | ✓ |
| Quarterly attribution report | ✗ | ✗ | ✓ |

**Technical implementation:** FastAPI backend + React frontend (after 6 months Streamlit validation). JWT authentication. Tier enforcement on every API endpoint.

---

### UC-25: Research Delivery Engine `[PHASE 2 — activate on SEBI RA registration]`

**Purpose:** Every signal delivered to clients is a formal research note. SEBI RA regulations require this. Ad-hoc WhatsApp messages without proper format are non-compliant.

**Research note format (SEBI RA compliant):**
```
RESEARCH NOTE — UniPro AI Research
SEBI RA Registration: INH[number]
Date: [timestamp]
Research Analyst: Mohit [surname]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STOCK: [SYMBOL] — [COMPANY NAME]
Sector: [NSE sector] | Market Cap: ₹[X]cr
Signal Tier: [1/2/3] | Pattern: [VCP/TightBase/Breakout]

ACTION: BUY on breakout above ₹[pivot]
Entry Zone: ₹[low] – ₹[high]
Stop Loss: ₹[stop] ([X]% below entry)
Position Size: [X]% of portfolio (2% risk rule)
Regime: [regime name] | Composite Score: [X]/100

KEY METRICS:
  RS Rank: [X]th percentile
  Momentum Quality: [X]% positive weeks (26W)
  Base Length: [X] weeks | Depth: [X]%
  Contractions: [X] | OBV Slope: [Rising/Flat]
  Monster Score: [X]/100 [if >= 60]
  SUE Proxy Active: [Yes/No] | EPS Growth YoY: [X]%

EARNINGS ALERT: [Results due in X days — exercise caution]
  OR: [Next results: [date] — [X] trading days away]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DISCLAIMER: This research is prepared by UniPro AI Research
(SEBI RA Reg. INH[number]). Registration does not imply SEBI
endorsement. Investing in equities involves risk of capital loss.
Past signals are not indicative of future performance. This note
is for informational purposes only and does not constitute
financial advice. Investors must assess their own suitability.
Full disclaimer: uniproadvisory.com/disclaimer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Delivery channels by tier:**
- Starter: WhatsApp text + portal
- Pro: WhatsApp formatted note + email + portal
- Institutional: All above + webhook push + REST API

**Archival:** Every research note stored in `research_notes` table with client_id, delivery timestamp, delivery channel, read confirmation. 5-year retention. Never deletable.

---

### UC-26: Client Communication Archive `[PHASE 2 — activate on SEBI RA registration]`

**Purpose:** SEBI requires all client communications archived for 5 years. Every WhatsApp, email, and portal message must be logged.

```sql
CREATE TABLE client_communications (
    id                  SERIAL PRIMARY KEY,
    client_id           VARCHAR(20),
    communication_date  TIMESTAMP NOT NULL,
    channel             VARCHAR(20),          -- whatsapp/email/portal/call
    direction           VARCHAR(10),          -- outbound/inbound
    subject             VARCHAR(200),
    content             TEXT,
    signal_id           INTEGER,              -- if related to a specific signal
    report_id           VARCHAR(50),          -- if related to a specific report
    is_research_note    BOOLEAN DEFAULT FALSE,
    delivered           BOOLEAN DEFAULT FALSE,
    read_confirmed      BOOLEAN DEFAULT FALSE,
    read_timestamp      TIMESTAMP,
    archived_at         TIMESTAMP DEFAULT NOW(),
    -- SEBI compliance
    cannot_delete       BOOLEAN DEFAULT TRUE,  -- immutable record
    retention_until     DATE                   -- 5 years from communication_date
);

CREATE INDEX idx_comm_client_date ON client_communications (client_id, communication_date DESC);
CREATE INDEX idx_comm_retention   ON client_communications (retention_until);
```

**Retention enforcement:**
```python
def enforce_retention_policy(db):
    """
    Called weekly. Flags records approaching 5-year retention window.
    Never deletes — only flags for potential archival to cold storage.
    SEBI requires 5-year retention minimum.
    Records marked cannot_delete = TRUE can never be purged by the system.
    """
    cutoff = date.today() - timedelta(days=365*5)
    approaching = db.query(
        "SELECT COUNT(*) FROM client_communications WHERE retention_until < %s",
        [date.today() + timedelta(days=90)]
    )
    if approaching > 0:
        alert_admin(f"{approaching} communication records approaching 5-year retention limit. Review archival policy.")
```

---

## COMPLIANCE LAYER — UC-27 through UC-30

---

### UC-27: Compliance Calendar `[PHASE 2 — activate on SEBI RA registration]`

**Purpose:** Auto-tracks all SEBI deadlines and regulatory requirements. Alerts at 30/14/7/1 days before each deadline. Never miss a filing.

```sql
CREATE TABLE compliance_calendar (
    id                  SERIAL PRIMARY KEY,
    event_name          VARCHAR(200),
    event_type          VARCHAR(50),    -- filing/renewal/disclosure/audit
    due_date            DATE,
    recurrence          VARCHAR(20),    -- annual/quarterly/monthly/once
    responsible_party   VARCHAR(100),
    description         TEXT,
    completed           BOOLEAN DEFAULT FALSE,
    completed_date      DATE,
    notes               TEXT
);
```

**Pre-populated SEBI RA events:**
```python
SEBI_RA_COMPLIANCE_EVENTS = [
    # Annual
    {'name': 'SEBI RA Licence Renewal', 'type': 'renewal', 'recurrence': 'annual',
     'description': 'File renewal application 3 months before expiry. Fee payment required.'},
    {'name': 'Annual Compliance Report', 'type': 'filing', 'recurrence': 'annual',
     'description': 'File annual compliance report with SEBI. Details of clients, complaints, research issued.'},
    {'name': 'Net Worth Certificate', 'type': 'filing', 'recurrence': 'annual',
     'description': 'CA-certified net worth certificate. Individual RA minimum ₹1 lakh.'},

    # Quarterly
    {'name': 'Complaints Report', 'type': 'filing', 'recurrence': 'quarterly',
     'description': 'Report of client complaints received and resolved. Nil report if no complaints.'},

    # Ongoing
    {'name': 'Client KYC Review', 'type': 'compliance', 'recurrence': 'annual',
     'description': 'Review KYC of all active clients annually. Update any expired documents.'},
    {'name': 'Conflict of Interest Disclosure Update', 'type': 'disclosure', 'recurrence': 'quarterly',
     'description': 'Update and re-disclose any stocks held personally by research analyst.'},
    {'name': 'SEBI Circular Review', 'type': 'monitoring', 'recurrence': 'monthly',
     'description': 'Check SEBI website for new circulars affecting RA operations.'},
]
```

---

### UC-28: Personal Trading Restriction Engine `[PHASE 2 — activate on SEBI RA registration]`

**Purpose:** SEBI RA regulations prohibit trading in stocks recommended to clients within a restricted window. This engine enforces the Chinese wall automatically.

**SEBI RA Regulation 16 — key requirements:**
- Research analyst must not trade in securities they recommend for 30 days before and after the recommendation
- Must disclose any personal holdings in recommended securities
- Must not front-run client recommendations

```python
def check_personal_trade_allowed(symbol, trade_type, as_of_date, db):
    """
    SEBI RA Regulation 16 compliance check.
    Called before any personal trade by Mohit.
    Returns: (allowed: bool, reason: str, earliest_allowed_date: date)
    """
    # Check if this stock has been recommended to clients in last 30 days
    recent_signals = db.query("""
        SELECT signal_date, tier FROM signals
        WHERE symbol = %s
        AND signal_date >= %s
        AND status = 'Confirmed'
    """, [symbol, as_of_date - timedelta(days=30)])

    if recent_signals:
        earliest = min(s['signal_date'] for s in recent_signals)
        earliest_allowed = earliest + timedelta(days=30)
        return False, f"Stock recommended to clients on {earliest}. Trade restricted until {earliest_allowed}.", earliest_allowed

    # Check if personal trade would be followed by a recommendation in next 30 days
    # (front-running prevention — harder to enforce but log the check)
    upcoming_signals = db.query("""
        SELECT signal_date FROM signals
        WHERE symbol = %s
        AND signal_date >= %s
        AND signal_date <= %s
        AND status IN ('Confirmed', 'Pending')
    """, [symbol, as_of_date, as_of_date + timedelta(days=30)])

    if upcoming_signals:
        return False, f"Pending client recommendation for {symbol}. Personal trade blocked (front-running prevention).", None

    return True, "Trade permitted — no client recommendation conflict.", None


def log_personal_trade(symbol, trade_type, price, quantity, as_of_date, db):
    """
    Log all personal trades by the research analyst.
    Required by SEBI RA regulations. Stored in audit trail.
    """
    db.execute("""
        INSERT INTO analyst_personal_trades
        (symbol, trade_type, price, quantity, trade_date, compliance_checked, allowed)
        VALUES (%s, %s, %s, %s, %s, TRUE, TRUE)
    """, [symbol, trade_type, price, quantity, as_of_date])
```

```sql
CREATE TABLE analyst_personal_trades (
    id                  SERIAL PRIMARY KEY,
    symbol              VARCHAR(20),
    trade_type          VARCHAR(10),    -- buy/sell
    price               DECIMAL(12,2),
    quantity            INTEGER,
    trade_date          DATE,
    compliance_checked  BOOLEAN DEFAULT TRUE,
    allowed             BOOLEAN,
    restriction_reason  TEXT,
    -- SEBI audit
    cannot_delete       BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW()
);
```

---

### UC-29: SEBI Audit Trail `[PHASE 2 — activate on SEBI RA registration]`

**Purpose:** Immutable, timestamped log of all research, signals, client communications, and personal trades. SEBI requires 5-year retention. Must be exportable for SEBI inspection.

```sql
CREATE TABLE sebi_audit_trail (
    id                  BIGSERIAL PRIMARY KEY,
    event_timestamp     TIMESTAMP NOT NULL DEFAULT NOW(),
    event_type          VARCHAR(50) NOT NULL,
    -- Types: signal_generated / signal_delivered / client_onboarded /
    --        report_generated / report_delivered / personal_trade /
    --        compliance_filing / system_config_change / parameter_change
    entity_type         VARCHAR(50),    -- signal/client/report/trade/parameter
    entity_id           VARCHAR(100),
    actor               VARCHAR(100),   -- 'system' or analyst name
    action              VARCHAR(200),
    details             JSONB,          -- full details of the event
    ip_address          VARCHAR(45),
    -- Immutability
    cannot_modify       BOOLEAN DEFAULT TRUE,
    cannot_delete       BOOLEAN DEFAULT TRUE,
    retention_until     DATE NOT NULL   -- 5 years from event_timestamp
);

-- Immutability trigger — prevents any UPDATE or DELETE
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'SEBI audit trail records are immutable. No modifications permitted.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_trail_immutable
    BEFORE UPDATE OR DELETE ON sebi_audit_trail
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
```

**Auto-populated on every:**
- Signal generated or delivered to client
- Client onboarded, upgraded, or cancelled
- Report generated or delivered
- Personal trade by analyst
- Settings.py parameter change (what changed, old value, new value)
- Pipeline failure or data quality alert
- Compliance filing submitted

---

### UC-30: Disclaimer Automation `[PHASE 2 — activate on SEBI RA registration]`

**Purpose:** Every client-facing output auto-appends the correct SEBI-mandated disclaimer. No manual disclaimer required. Disclaimer is versioned and updates when SEBI rules change.

```python
SEBI_DISCLAIMER = {
    'version': '2.0',
    'effective_date': '2024-01-01',
    'short': (
        "UniPro AI Research | SEBI RA Reg. INH[number] | "
        "Past performance ≠ future results | "
        "Not financial advice | Full disclaimer: uniproadvisory.com/disclaimer"
    ),
    'full': (
        "This research report/signal is prepared by UniPro AI Research, "
        "a SEBI Registered Research Analyst (Registration No. INH[number]). "
        "SEBI registration does not imply endorsement of the analyst's views "
        "or the accuracy of the research. Equity investments are subject to "
        "market risk. Past performance is not indicative of future returns. "
        "This research is for informational purposes only and does not "
        "constitute investment advice or a solicitation to buy or sell securities. "
        "Investors must make independent assessments of their financial situation, "
        "investment objectives, and risk tolerance before acting on this research. "
        "The research analyst may hold positions in securities mentioned herein. "
        "Full conflict of interest disclosure available at: "
        "uniproadvisory.com/disclosures | Grievance: grievance@uniproadvisory.com"
    )
}

def append_disclaimer(content, format_type='short'):
    """
    Append correct SEBI disclaimer to any client-facing content.
    Always uses current version from SEBI_DISCLAIMER dict.
    When SEBI updates disclaimer requirements: update dict only.
    All outputs automatically use new version.
    """
    disclaimer = SEBI_DISCLAIMER[format_type]
    if format_type == 'short':
        return f"{content}\n\n---\n{disclaimer}"
    else:
        return f"{content}\n\n{'='*60}\nDISCLAIMER\n{'='*60}\n{disclaimer}"
```

---

## FUND OPERATIONS LAYER — UC-31 through UC-33

---

### UC-31: NAV Calculation Engine `[PHASE 5 — activate on AIF/PMS licence]`

**Purpose:** Daily NAV (Net Asset Value) per unit for AIF or PMS structure. Regulatory requirement — investors receive daily NAV.

```python
def calculate_daily_nav(db, as_of_date, fund_id):
    """
    Daily NAV calculation — AIF/PMS regulatory requirement.
    NAV = (Total Assets - Total Liabilities) / Units Outstanding

    Total Assets:
      + Cash and equivalents
      + Market value of all open positions (using adj_close)
      + Accrued dividends receivable
      - Unrealised losses (already in market value)

    Total Liabilities:
      + Accrued management fee (daily accrual)
      + Accrued performance fee above high watermark
      + Outstanding redemption payables
      + Other payables
    """
    # Market value of positions
    open_pos   = get_open_positions(db, fund_id, as_of_date)
    market_val = sum(
        p['shares'] * get_adj_close(db, p['symbol'], as_of_date)
        for p in open_pos
    )

    # Cash
    cash = get_fund_cash_balance(db, fund_id, as_of_date)

    # Accrued fees
    mgmt_fee_accrued   = calculate_accrued_mgmt_fee(db, fund_id, as_of_date)
    perf_fee_accrued   = calculate_accrued_perf_fee(db, fund_id, as_of_date)

    # NAV
    total_assets      = market_val + cash
    total_liabilities = mgmt_fee_accrued + perf_fee_accrued
    nav_total         = total_assets - total_liabilities
    units_outstanding = get_units_outstanding(db, fund_id)
    nav_per_unit      = nav_total / units_outstanding if units_outstanding > 0 else 0

    store_nav(db, fund_id, as_of_date, nav_per_unit, nav_total,
              market_val, cash, mgmt_fee_accrued, perf_fee_accrued)

    return nav_per_unit
```

```sql
CREATE TABLE fund_nav (
    fund_id         VARCHAR(20),
    nav_date        DATE,
    nav_per_unit    DECIMAL(14,6),
    nav_total       DECIMAL(18,2),
    market_value    DECIMAL(18,2),
    cash_balance    DECIMAL(18,2),
    mgmt_fee_accr   DECIMAL(14,2),
    perf_fee_accr   DECIMAL(14,2),
    units_outstanding DECIMAL(14,4),
    PRIMARY KEY (fund_id, nav_date)
);
```

---

### UC-32: Fee Calculation Engine `[PHASE 5 — activate on AIF/PMS licence]`

**Purpose:** Accurate, auditable fee calculation. Management fee and performance fee with high watermark.

```python
FEE_STRUCTURE = {
    'management_fee_annual_pct': 2.0,    # 2% per annum, accrued daily
    'performance_fee_pct':       20.0,   # 20% of profits above hurdle
    'hurdle_rate_annual_pct':    10.0,   # 10% annual hurdle (Nifty 50 proxy)
    'high_watermark':            True,   # Never charge perf fee below prior peak NAV
    'crystallisation':           'annual' # Performance fee crystallised annually
}

def calculate_accrued_mgmt_fee(db, fund_id, as_of_date):
    """
    Management fee accrues daily.
    Daily rate = annual_pct / 252
    Applied to beginning-of-day NAV (not end-of-day to avoid circularity)
    """
    beginning_nav = get_nav(db, fund_id, as_of_date - timedelta(days=1))
    daily_rate    = FEE_STRUCTURE['management_fee_annual_pct'] / 100 / 252
    daily_accrual = beginning_nav * daily_rate
    return daily_accrual


def calculate_performance_fee(db, fund_id, as_of_date):
    """
    Performance fee charged only above:
    1. High watermark (prior peak NAV per unit)
    2. Hurdle rate (10% annual — pro-rated)
    
    High watermark prevents charging performance fee on recovering
    from a loss. Investors never pay twice for the same gains.
    """
    current_nav    = get_nav(db, fund_id, as_of_date)
    high_watermark = get_high_watermark(db, fund_id)
    hurdle_nav     = get_hurdle_nav(db, fund_id, as_of_date)  # HWM * (1 + hurdle)

    if current_nav <= high_watermark or current_nav <= hurdle_nav:
        return 0.0  # below watermark or hurdle — no performance fee

    # Fee only on gains above BOTH watermark AND hurdle
    taxable_gain   = (current_nav - max(high_watermark, hurdle_nav))
    total_units    = get_units_outstanding(db, fund_id)
    perf_fee       = taxable_gain * total_units * (FEE_STRUCTURE['performance_fee_pct'] / 100)

    return perf_fee
```

---

### UC-33: Investor Capital Allocation `[PHASE 5 — activate on AIF/PMS licence]`

**Purpose:** Track each investor's units, entry NAV, current value, and redemption processing.

```sql
CREATE TABLE investor_accounts (
    investor_id         VARCHAR(20) PRIMARY KEY,
    name                VARCHAR(100),
    pan                 VARCHAR(10),
    kyc_status          VARCHAR(20),
    fund_id             VARCHAR(20),
    units_held          DECIMAL(14,4),
    entry_nav           DECIMAL(14,6),    -- NAV at which investor entered
    entry_date          DATE,
    committed_capital   DECIMAL(18,2),    -- total capital committed
    drawn_capital       DECIMAL(18,2),    -- capital actually deployed
    current_value       DECIMAL(18,2),    -- current market value of units
    unrealised_pnl      DECIMAL(18,2),
    accrued_mgmt_fee    DECIMAL(14,2),
    accrued_perf_fee    DECIMAL(14,2),
    last_updated        DATE
);

CREATE TABLE redemption_requests (
    id                  SERIAL PRIMARY KEY,
    investor_id         VARCHAR(20),
    request_date        DATE,
    units_requested     DECIMAL(14,4),
    redemption_nav      DECIMAL(14,6),    -- NAV on redemption date
    redemption_value    DECIMAL(18,2),
    status              VARCHAR(20),      -- pending/processing/completed/gated
    gating_reason       TEXT,             -- if redemptions are gated
    processed_date      DATE
);
```

**Redemption gate rule (AIF standard):**
```python
def check_redemption_gate(db, fund_id, as_of_date):
    """
    Suspend redemptions if:
    - Portfolio drawdown > 15% from peak NAV
    - Liquidity ratio < 20% (less than 20% of portfolio in liquid positions)
    - Regime is Full Bear
    """
    current_nav    = get_nav(db, fund_id, as_of_date)
    peak_nav       = get_peak_nav(db, fund_id)
    drawdown       = (peak_nav - current_nav) / peak_nav
    liquidity_pct  = get_portfolio_liquidity(db, fund_id, as_of_date)
    regime         = get_current_regime(db, as_of_date)

    if drawdown > 0.15:
        return True, f"Redemptions gated: portfolio drawdown {drawdown:.1%} exceeds 15% threshold"
    if liquidity_pct < 0.20:
        return True, f"Redemptions gated: portfolio liquidity {liquidity_pct:.1%} below 20% minimum"
    if regime == 'Full Bear':
        return True, "Redemptions gated: Full Bear regime — protecting remaining capital"
    return False, "Redemptions open"
```

---

## EXECUTION INFRASTRUCTURE LAYER — UC-34 through UC-35

---

### UC-34: Order Management System `[PHASE 3 — activate at go-live]`

**Purpose:** Queue, route, track, and confirm all orders. Handle partial fills. Integrate with Zerodha Kite Connect for personal account. Expandable to multi-broker.

```python
class OrderManagementSystem:
    """
    OMS — routes orders, tracks fills, handles partials.
    Phase 3: Zerodha Kite Connect for personal account.
    Phase 5: Multi-broker for fund execution.
    """

    def place_order(self, symbol, order_type, quantity, price,
                    signal_id, as_of_date):
        """
        Place order via configured broker.
        Logs order pre-execution for audit trail.
        Includes pre-trade Turnaround Watch block (NEW v16).
        """
        order_id = generate_order_id()

        # ── PRE-TRADE CHECK: Turnaround Watch block (NEW v16) ────────
        # Prevents manual entry on stocks that are on Turnaround Watch
        # but have not yet generated a formal Tier 1/2 signal.
        # Enforces system discipline — Turnaround Watch is monitoring
        # only, not a buy signal.
        if order_type in ('entry', 'manual_entry') and symbol:
            watch_entry = get_turnaround_watch_status(symbol, as_of_date)
            if watch_entry and watch_entry['is_active']:
                # Check if a formal Tier 1 or Tier 2 signal exists
                has_signal = check_active_tier_signal(symbol, as_of_date)
                if not has_signal:
                    # BLOCK the order
                    block_reason = (
                        f"{symbol} is on Turnaround Watch. "
                        f"EPS block not yet cleared "
                        f"({watch_entry['quarters_to_clearance']} quarter(s) remaining). "
                        f"Entry blocked until system generates Tier 1 or Tier 2 signal. "
                        f"Do NOT override manually."
                    )
                    # Log blocked attempt in SEBI audit trail
                    log_blocked_order_attempt(
                        order_id   = order_id,
                        symbol     = symbol,
                        reason     = 'turnaround_watch_block',
                        detail     = block_reason,
                        as_of_date = as_of_date
                    )
                    # Alert Mohit
                    send_whatsapp(MOHIT_PHONE,
                        f"🚫 ORDER BLOCKED — {symbol}\n"
                        f"{block_reason}\n"
                        f"Check dashboard for entry trigger conditions."
                    )
                    raise OrderBlockedError(block_reason)

        # ── Log pre-execution (SEBI audit requirement) ───────────────
        log_order_intent(order_id, symbol, order_type, quantity,
                         price, signal_id, as_of_date)

        # ── Route to broker ───────────────────────────────────────────
        if ENVIRONMENT == 'LIVE':
            broker_order_id = self.kite.place_order(
                tradingsymbol    = symbol,
                exchange         = 'NSE',
                transaction_type = 'BUY' if order_type == 'entry' else 'SELL',
                quantity         = quantity,
                order_type       = 'MARKET',
                product          = 'CNC'
            )
        else:
            broker_order_id = f"PAPER_{order_id}"

        store_order(order_id, broker_order_id, symbol, order_type,
                    quantity, price, signal_id, status='PLACED')
        return order_id

    def handle_partial_fill(self, order_id, filled_quantity,
                             fill_price, remaining):
        """
        Partial fills: position is entered at filled quantity.
        Remaining unfilled: cancel if fill < 80% of intended.
                           Re-queue if fill >= 80%.
        """
        fill_rate = filled_quantity / get_order_quantity(order_id)

        if fill_rate >= 0.80:
            # Acceptable fill — proceed with partial position
            update_order_status(order_id, 'PARTIAL_FILLED',
                                filled_quantity, fill_price)
            update_position_size(order_id, filled_quantity, fill_price)
            log_slippage(order_id, fill_price, get_expected_price(order_id))
        else:
            # Poor fill — cancel remainder, log as partial
            cancel_remaining(order_id, remaining)
            update_order_status(order_id, 'POOR_FILL_CANCELLED',
                                filled_quantity, fill_price)
            alert_mohit(f"Poor fill on {get_symbol(order_id)}: "
                       f"{fill_rate:.0%} filled at ₹{fill_price}")
```

```sql
CREATE TABLE orders (
    order_id            VARCHAR(30) PRIMARY KEY,
    broker_order_id     VARCHAR(50),
    symbol              VARCHAR(20),
    order_type          VARCHAR(20),     -- entry/exit/trim/rebalance
    quantity_intended   INTEGER,
    quantity_filled     INTEGER DEFAULT 0,
    price_expected      DECIMAL(12,2),   -- signal price (next-day open assumption)
    price_filled        DECIMAL(12,2),
    slippage_pct        DECIMAL(8,4),
    signal_id           INTEGER,
    order_date          DATE,
    status              VARCHAR(20),     -- placed/filled/partial/cancelled/failed
    broker             VARCHAR(20),      -- zerodha/paper
    environment         VARCHAR(10),     -- live/paper/dev
    created_at          TIMESTAMP DEFAULT NOW()
);

-- Blocked order attempts — SEBI audit trail (NEW v16)
-- Every manually attempted entry blocked by a pre-trade check is logged here.
-- Immutable. Provides evidence that system discipline was maintained.
-- If SEBI or a client asks "did you follow your own rules?" — this table
-- shows every time the system enforced its own rules against override.
CREATE TABLE blocked_order_attempts (
    id                  SERIAL PRIMARY KEY,
    attempt_timestamp   TIMESTAMP NOT NULL DEFAULT NOW(),
    symbol              VARCHAR(20),
    order_type          VARCHAR(20),
    block_reason        VARCHAR(50),   -- 'turnaround_watch_block'
    block_detail        TEXT,
    environment         VARCHAR(10),
    cannot_delete       BOOLEAN DEFAULT TRUE,
    retention_until     DATE          -- 5 years from attempt_timestamp
);

-- Data quality alerts — pipeline integrity (NEW v16.1)
-- Every data gap, feed failure, or quality anomaly is logged here.
-- Called by handle_missing_fundamentals() when Screener.in data is absent
-- or incomplete for a stock. Also populated by BSE cross-validation when
-- NSE/BSE price divergence exceeds 0.5%, and by adjusted-close verification
-- when a corporate action produces an unexpected price adjustment.
--
-- Developer: log_data_quality_alert() must write here for EVERY data issue.
-- Pipeline step 3 (data validation) reads this table and halts the pipeline
-- if any CRITICAL severity alert has not been resolved within 24 hours.
CREATE TABLE data_quality_alerts (
    id                  SERIAL PRIMARY KEY,
    alert_timestamp     TIMESTAMP NOT NULL DEFAULT NOW(),
    symbol              VARCHAR(20),             -- NULL for market-level alerts
    alert_type          VARCHAR(50) NOT NULL,
    -- Values:
    --   'screener_missing_all'     — no Screener.in record for symbol
    --   'screener_missing_field'   — specific field absent in record
    --   'bse_nse_price_diverge'    — NSE vs BSE adj_close diff > 0.5%
    --   'adj_close_anomaly'        — adjusted close jump > 20% not explained by known CA
    --   'feed_delay'               — NSE bhav copy not available by 4:30 PM
    --   'reporting_date_future'    — reporting_date stamped in the future (bad data)
    --   'duplicate_quarterly'      — duplicate period_end_date for same symbol
    severity            VARCHAR(10) NOT NULL,
    -- Values: 'CRITICAL' / 'WARNING' / 'INFO'
    -- CRITICAL: halts pipeline after 24h if unresolved (hard block cannot be evaluated)
    -- WARNING:  pipeline continues; signal for that stock suppressed until resolved
    -- INFO:     logged only; no pipeline impact
    detail              TEXT,
    missing_field       VARCHAR(50),             -- which field is missing if applicable
    expected_value      VARCHAR(100),            -- what the system expected
    actual_value        VARCHAR(100),            -- what was found (or NULL if missing)
    resolved            BOOLEAN DEFAULT FALSE,
    resolved_timestamp  TIMESTAMP,
    resolved_by         VARCHAR(50),             -- 'auto_refetch' / 'manual_mohit' / 'dev'
    resolution_note     TEXT,
    as_of_date          DATE,
    pipeline_run_id     VARCHAR(30)              -- links to pipeline execution log
);

-- Indexes for fast pipeline queries
CREATE INDEX idx_dqa_unresolved  ON data_quality_alerts (resolved, alert_timestamp DESC);
CREATE INDEX idx_dqa_symbol      ON data_quality_alerts (symbol, as_of_date DESC);
CREATE INDEX idx_dqa_critical    ON data_quality_alerts (severity, resolved) WHERE severity = 'CRITICAL';
```

---

### UC-35: Execution Quality Report `[PHASE 3 — activate at go-live]`

**Purpose:** Daily and monthly slippage analysis. Confirms the 0.5% slippage assumption in backtesting is still valid live.

```python
def generate_execution_quality_report(db, period_start, period_end):
    """
    Execution quality analysis.
    Key question: is live slippage consistent with backtest assumption (0.5%)?
    If live slippage consistently > 0.7%: raise slippage assumption in backtest
    and re-run Test 15 cost sensitivity to confirm system remains viable.
    """
    orders = get_orders_in_range(db, period_start, period_end)

    entry_slippage = [o['slippage_pct'] for o in orders if o['order_type'] == 'entry']
    exit_slippage  = [o['slippage_pct'] for o in orders if o['order_type'] == 'exit']

    report = {
        'period':               f"{period_start} to {period_end}",
        'total_orders':         len(orders),
        'entry_avg_slippage':   np.mean(entry_slippage) if entry_slippage else 0,
        'exit_avg_slippage':    np.mean(exit_slippage) if exit_slippage else 0,
        'max_slippage':         max([o['slippage_pct'] for o in orders], default=0),
        'slippage_assumption':  0.005,   # 0.5% from backtest
        'slippage_breach_count': sum(1 for s in entry_slippage if s > 0.007),

        # Market impact by position size
        'small_pos_slippage':  avg_slippage_by_size(orders, size_bucket='small'),
        'large_pos_slippage':  avg_slippage_by_size(orders, size_bucket='large'),
    }

    # Alert if slippage assumption is being exceeded consistently
    if report['entry_avg_slippage'] > 0.007:   # > 0.7%
        trigger_slippage_review_alert(report)

    return report
```

---

## TECHNOLOGY OPERATIONS LAYER — UC-36 through UC-38

---

### UC-36: Pipeline Monitoring and Alerting `[PHASE 1 — activate immediately]`

**Purpose:** Every pipeline step is monitored. Silent failures are not acceptable in a live trading system.

```sql
CREATE TABLE pipeline_log (
    id              SERIAL PRIMARY KEY,
    run_date        DATE,
    step_number     INTEGER,
    step_name       VARCHAR(100),
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    duration_seconds DECIMAL(8,2),
    expected_max_seconds INTEGER,
    status          VARCHAR(20),    -- running/completed/failed/skipped
    records_processed INTEGER,
    error_message   TEXT,
    environment     VARCHAR(10)
);
```

```python
PIPELINE_STEP_LIMITS = {
    1:  10,    # holiday check — 10 seconds max
    2:  300,   # bhav download — 5 minutes max
    10: 600,   # indicator calculation — 10 minutes max
    18: 360,   # VCP detection — 6 minutes max
}

def monitor_pipeline_step(step_number, step_name, func, *args):
    """
    Wraps every pipeline step with monitoring.
    Logs start, end, duration.
    Alerts if step fails or exceeds expected time.
    """
    started   = datetime.now()
    log_step_start(step_number, step_name, started)

    try:
        result = func(*args)
        duration = (datetime.now() - started).seconds
        log_step_complete(step_number, step_name, duration)

        # Alert if step takes longer than expected
        max_allowed = PIPELINE_STEP_LIMITS.get(step_number, 300)
        if duration > max_allowed:
            send_whatsapp(MOHIT_PHONE,
                f"⚠️ Pipeline step {step_number} ({step_name}) took {duration}s "
                f"vs expected {max_allowed}s max. Check for data issues.")
        return result

    except Exception as e:
        log_step_failure(step_number, step_name, str(e))
        send_whatsapp(MOHIT_PHONE,
            f"🚨 PIPELINE FAILURE — Step {step_number} ({step_name}): {str(e)[:200]}")
        send_email(DEVELOPER_EMAIL,
            f"Pipeline failure step {step_number}", traceback.format_exc())
        raise  # re-raise so pipeline halts
```

---

### UC-37: Checkpoint and Recovery System `[PHASE 1 — activate immediately]`

**Purpose:** If pipeline crashes midway (server restart, data download failure, etc.), it resumes from the last completed checkpoint rather than restarting from step 1. Prevents double-processing and data integrity issues.

```python
def get_last_checkpoint(db, run_date):
    """
    Returns the last successfully completed pipeline step for today's run.
    If no checkpoint found: start from step 1.
    """
    result = db.query("""
        SELECT MAX(step_number) as last_step
        FROM pipeline_log
        WHERE run_date = %s AND status = 'completed'
    """, [run_date])
    return result[0]['last_step'] if result and result[0]['last_step'] else 0


def run_daily_pipeline(db, as_of_date):
    """
    Main pipeline runner with checkpoint/recovery.
    Skips already-completed steps on restart.
    """
    last_checkpoint = get_last_checkpoint(db, as_of_date)

    all_steps = get_all_pipeline_steps()  # ordered list of (step_num, step_name, func)

    for step_num, step_name, step_func in all_steps:
        if step_num <= last_checkpoint:
            log(f"Step {step_num} ({step_name}): skipped — already completed")
            continue

        # Run with monitoring
        monitor_pipeline_step(step_num, step_name, step_func, db, as_of_date)

    log(f"Pipeline complete for {as_of_date}")
```

---

### UC-38: Environment Management `[PHASE 3 — activate at go-live]`

**Purpose:** Three completely separate environments. No cross-contamination. No accidental live trades from dev or paper environment.

```python
# config/settings.py
ENVIRONMENT = 'PAPER'   # 'DEV' / 'PAPER' / 'LIVE'

# Environment-specific database connections
DATABASE_CONFIG = {
    'DEV':   {'host': 'localhost', 'db': 'momentumedge_dev'},
    'PAPER': {'host': 'server',    'db': 'momentumedge_paper'},
    'LIVE':  {'host': 'server',    'db': 'momentumedge_live'},
}

# Execution guard — prevents live orders from non-LIVE environment
def place_order_guard(symbol, quantity, order_type):
    if ENVIRONMENT != 'LIVE':
        log(f"[{ENVIRONMENT}] Simulated order: {order_type} {quantity} {symbol}")
        return f"SIMULATED_{generate_order_id()}"
    else:
        # Real execution only in LIVE environment
        return kite_execute(symbol, quantity, order_type)
```

**Environment rules:**
- DEV: developer testing. Synthetic or historical data only. Never live NSE feed.
- PAPER: live NSE data feed. Real signals. No real money. Separate database from LIVE.
- LIVE: real capital. Requires explicit `ENVIRONMENT = 'LIVE'` in settings. Any change to settings.py logged in SEBI audit trail.

---

## BUSINESS INTELLIGENCE LAYER — UC-39 through UC-40

---

### UC-39: Strategy Decay Detection `[PHASE 3 — activate at go-live]`

**Purpose:** Automatically detect when live performance is diverging from the backtest distribution. Early warning before losses compound.

```python
def check_strategy_decay(db, as_of_date):
    """
    Weekly statistical test comparing live performance against backtest.
    If live performance diverges beyond 2 standard deviations for
    4 consecutive weeks: STRATEGY DECAY WARNING.

    This is the single most important live monitoring function.
    If it fires: stop taking new positions, review system, do not ignore.
    """
    # Get rolling 90-day live metrics
    live_win_rate   = calculate_rolling_win_rate(db, as_of_date, days=90)
    live_avg_win    = calculate_rolling_avg_win(db, as_of_date, days=90)
    live_avg_loss   = calculate_rolling_avg_loss(db, as_of_date, days=90)
    live_sharpe_90d = calculate_rolling_sharpe(db, as_of_date, days=90)

    # Get backtest distribution (mean and std from Test 10)
    bt = get_backtest_distribution(db)

    # Z-scores vs backtest distribution
    z_win_rate = (live_win_rate - bt['win_rate_mean']) / bt['win_rate_std']
    z_sharpe   = (live_sharpe_90d - bt['sharpe_mean'])  / bt['sharpe_std']

    decay_signals = []
    if z_win_rate < -2.0:
        decay_signals.append(f"Win rate {live_win_rate:.1%} is {abs(z_win_rate):.1f} std below backtest mean")
    if z_sharpe < -2.0:
        decay_signals.append(f"Sharpe {live_sharpe_90d:.2f} is {abs(z_sharpe):.1f} std below backtest mean")

    # Persist counter — only warn after 4 consecutive weeks
    if decay_signals:
        increment_decay_counter(db, as_of_date)
        consecutive_weeks = get_decay_counter(db, as_of_date)

        if consecutive_weeks >= 4:
            # FIRE THE WARNING
            alert_text = (
                f"🚨 STRATEGY DECAY WARNING — {consecutive_weeks} consecutive weeks of degradation\n"
                + "\n".join(decay_signals)
                + "\n\nAction required: Stop new positions. Review system. Do not ignore."
            )
            send_whatsapp(MOHIT_PHONE, alert_text)
            send_email(MOHIT_EMAIL, "STRATEGY DECAY WARNING", alert_text)
            log_decay_event(db, as_of_date, decay_signals, consecutive_weeks)
    else:
        reset_decay_counter(db, as_of_date)  # consecutive run broken
```

---

### UC-40: Signal Quality Trends `[PHASE 3 — activate at go-live]`

**Purpose:** Rolling analysis of which signals are working live and which are degrading. Answers the question "is this signal still valid in current market conditions?" before the damage shows in overall P&L.

```python
def calculate_signal_quality_trends(db, as_of_date, lookback_days=90):
    """
    Rolling 90-day win rate broken down by:
    - Signal type (VCP / TightBase / Breakout)
    - Tier at entry (1 / 2 / 3)
    - Regime at entry (Strong Bull / Bull / Weak / Bear)
    - Sector at entry (top-3 / mid / bottom-3)
    - Monster score at entry (>= 80 / 60-80 / < 60)
    - SUE proxy active at entry (yes / no)

    Used in: dashboard panel, weekly report, quarterly attribution.
    Alert if any category drops below 35% win rate for 4+ consecutive weeks.
    """
    results = {}

    for signal_type in ['VCP', 'TightBase', 'Breakout']:
        results[f'win_rate_{signal_type}'] = calculate_win_rate_filtered(
            db, as_of_date, lookback_days, pattern_type=signal_type)

    for tier in [1, 2, 3]:
        results[f'win_rate_tier{tier}'] = calculate_win_rate_filtered(
            db, as_of_date, lookback_days, tier_at_entry=tier)

    for regime in ['Strong Bull', 'Bull', 'Weak', 'Bear']:
        results[f'win_rate_{regime.replace(" ", "_")}'] = calculate_win_rate_filtered(
            db, as_of_date, lookback_days, regime_at_entry=regime)

    results['win_rate_monster_high']   = calculate_win_rate_filtered(
        db, as_of_date, lookback_days, monster_score_min=80)
    results['win_rate_monster_med']    = calculate_win_rate_filtered(
        db, as_of_date, lookback_days, monster_score_min=60, monster_score_max=79)
    results['win_rate_sue_active']     = calculate_win_rate_filtered(
        db, as_of_date, lookback_days, sue_bonus_active=True)
    results['win_rate_sue_inactive']   = calculate_win_rate_filtered(
        db, as_of_date, lookback_days, sue_bonus_active=False)

    # Alert if any category below 35% for 4 consecutive weeks
    for key, win_rate in results.items():
        if win_rate < 0.35:
            check_and_alert_signal_degradation(db, key, win_rate, as_of_date)

    return results
```

---

## ADDITIONAL SCHEMA — v15 New Tables

```sql
-- Reporting archive
CREATE TABLE report_archive (
    id              SERIAL PRIMARY KEY,
    report_date     DATE,
    report_type     VARCHAR(20),    -- daily/weekly/monthly/quarterly/annual
    version         VARCHAR(10),
    content_md      TEXT,
    pdf_path        VARCHAR(500),
    delivered_to    JSONB,          -- list of delivery channels/recipients
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Research notes (SEBI RA requirement)
CREATE TABLE research_notes (
    id              SERIAL PRIMARY KEY,
    note_date       TIMESTAMP,
    signal_id       INTEGER REFERENCES signals(id),
    symbol          VARCHAR(20),
    note_content    TEXT,
    disclaimer_version VARCHAR(10),
    sebi_ra_number  VARCHAR(20),
    delivered_to    JSONB,
    cannot_delete   BOOLEAN DEFAULT TRUE,
    retention_until DATE
);

-- Pipeline checkpoint
CREATE INDEX idx_pipeline_date_step ON pipeline_log (run_date, step_number);

-- Strategy decay tracking
CREATE TABLE strategy_decay_log (
    id                  SERIAL PRIMARY KEY,
    check_date          DATE,
    consecutive_weeks   INTEGER,
    decay_signals       JSONB,
    warning_fired       BOOLEAN DEFAULT FALSE,
    resolved_date       DATE
);

-- Turnaround Watch (NEW v16)
CREATE TABLE turnaround_watch (
    symbol                  VARCHAR(20),
    first_alert_date        DATE,
    last_updated            DATE,
    current_price           DECIMAL(12,2),
    first_positive_eps      DECIMAL(10,2),
    eps_improvement_4q      DECIMAL(10,2),
    neg_eps_quarters        INTEGER,
    revenue_growth_yoy      DECIMAL(8,4),
    quarters_to_clearance   INTEGER,
    consecutive_pos_eps     INTEGER DEFAULT 0,     -- resets if EPS dips negative again
    is_active               BOOLEAN DEFAULT TRUE,
    entry_signal_fired      BOOLEAN DEFAULT FALSE,
    entry_signal_date       DATE,
    entry_signal_price      DECIMAL(12,2),
    hard_block_suppressed   BOOLEAN DEFAULT FALSE,
    suppression_reason      VARCHAR(50),           -- which block caused suppression
    -- Values: 'pledge_pct' / 'sebi_fine_24m' / 'business_pivot' /
    --         'ocf_negative' / 'multiple' — audit trail clarity
    notes                   TEXT,
    PRIMARY KEY (symbol, first_alert_date)
);

CREATE INDEX idx_turnaround_active ON turnaround_watch (is_active, last_updated DESC);

-- Signal quality trends
CREATE TABLE signal_quality_trends (
    check_date          DATE,
    dimension           VARCHAR(50),   -- signal_type/tier/regime/monster/sue
    dimension_value     VARCHAR(50),
    win_rate_90d        DECIMAL(5,4),
    trade_count         INTEGER,
    alert_fired         BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (check_date, dimension, dimension_value)
);

-- Analyst personal trades (SEBI RA compliance)
CREATE TABLE analyst_personal_trades (
    id                  SERIAL PRIMARY KEY,
    symbol              VARCHAR(20),
    trade_type          VARCHAR(10),
    price               DECIMAL(12,2),
    quantity            INTEGER,
    trade_date          DATE,
    compliance_checked  BOOLEAN DEFAULT TRUE,
    allowed             BOOLEAN,
    restriction_reason  TEXT,
    cannot_delete       BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- Fund NAV (AIF/PMS)
-- (see UC-31 above)

-- Investor accounts (AIF/PMS)
-- (see UC-33 above)

-- Redemption requests (AIF/PMS)
-- (see UC-33 above)
```

---

## 5. Exit Framework Simulation Results

> v12 adds no new stock simulations. All exit simulation evidence is carried forward from v11.

**Force Motors (FORCEMOT) — Entry ₹2,500 Jan 2023**

| Date | Price | Gain | Phase | Position | Event |
|---|---|---|---|---|---|
| Jan-23 | ₹2,500 | 0% | 1 | 100% | ENTRY |
| Mar-23 | ₹2,900 | +16% | 1 | 100% | Phase 1 — prove-it |
| Jun-23 | ₹3,500 | +40% | 2 | 100% | HOLD — let it run |
| Sep-23 | ₹4,800 | +92% | 2 | 100% | HOLD — no DMA exits fire |
| Dec-23 | ₹6,500 | +160% | 3 | 100% | HOLD — working compounder |
| Mar-24 | ₹8,500 | +240% | 4 | 75% | SELL 25% at first ATH |
| Jun-24 | ₹11,000 | +340% | 4 | 50% | SELL 25% at second ATH |
| Sep-24 | ₹15,000 | +500% | 4 | 50% | HOLD — monster run |
| Dec-24 | ₹20,000 | +700% | 4 | 50% | HOLD — monster run |
| Feb-25 | ₹23,000 | +820% | 4 | 50% | HOLD — monster run |
| May-25 | ₹26,000 | +940% | 4 | 50% | HOLD — near ATH |
| Jun-25 | ₹26,450 | +958% | 4 | 50% | ATH ₹26,450 |
| Sep-25 | ₹22,000 | +780% | 4 | 0% | EXIT — 10-week MA breach |

Result: Old system (MA200 exit) = ₹18,000 → 7.2x. v11/v12 framework = ₹22,000 → 8.8x.

**v12 note:** Force Motors would have scored high on the monster score (RS rank > 90, multiple prior bases, smooth trend, sector leadership). The monster override would have applied Phase 4 rules even during Phase 2 — producing identical holds but with explicit framework justification.

**Himadri Speciality Chemical (HIMADRI) — Entry ₹80 Aug 2020**

| Date | Price | Gain | Phase | Position | Event |
|---|---|---|---|---|---|
| Aug-20 | ₹80 | 0% | 1 | 100% | ENTRY |
| Oct-20 | ₹100 | +25% | 2 | 100% | HOLD — let it run |
| Jan-21 | ₹150 | +88% | 2 | 100% | HOLD — no 50DMA-ATR breach |
| Apr-21 | ₹220 | +175% | 3 | 100% | HOLD — compounder |
| Aug-21 | ₹300 | +275% | 4 | 75% | SELL 25% at first ATH |
| Sep-21 | ₹450 | +462% | 4 | 50% | SELL 25% at second ATH |
| Oct-21 | ₹550 | +588% | 4 | 50% | HOLD — 10-week MA holds |
| Nov-21 | ₹580 | +625% | 4 | 50% | HOLD |
| Dec-21 | ₹600 | +650% | 4 | 50% | HOLD — near ATH |
| Feb-22 | ₹520 | +550% | 4 | 0% | EXIT — 10-week trail fires |

**What the Simulations Prove:**
1. Phase-based framework is correct — Force Motors held through every correction between ₹2,500 and ₹20,000. Fixed DMA rule kills the 8.8x return at 3–4x.
2. ATH partial crystallisation works — both stocks had 25%+25% sold at strong prices before correction hit.
3. Climax run at 50% is right — Himadri's parabolic phase correctly identified.
4. 50DMA−1.5ATR filter prevents false exits — normal corrections in both stocks did not breach volatility-adjusted threshold.
5. MA200 is the backstop — never fired as primary exit in either stock.
6. 10-week MA is correct for Phase 4 — better exit than waiting for MA200.

---

## 6. Database Schema

```sql
-- ─────────────────────────────────────────────
-- CORE TABLES
-- ─────────────────────────────────────────────
CREATE TABLE stocks (
    symbol                   VARCHAR(20) PRIMARY KEY,  -- NSE symbol (primary)
    bse_code                 VARCHAR(10),              -- BSE scrip code (cross-reference, future)
    name                     VARCHAR(100),
    isin                     VARCHAR(20) UNIQUE,       -- ISIN = bridge between NSE and BSE
    sector                   VARCHAR(50),              -- NSE sector classification (22 groups)
    industry                 VARCHAR(50),              -- NSE industry classification (80 sub-groups)
    listing_date             DATE,
    market_cap_cr            DECIMAL(14,2),
    free_float_pct           DECIMAL(5,2),
    avg_daily_tv_cr          DECIMAL(10,2),
    is_asm                   BOOLEAN DEFAULT FALSE,
    is_esm                   BOOLEAN DEFAULT FALSE,
    is_financial             BOOLEAN DEFAULT FALSE,
    is_psu                   BOOLEAN DEFAULT FALSE,
    is_infrastructure_sector BOOLEAN DEFAULT FALSE,
    is_fii_capped_sector     BOOLEAN DEFAULT FALSE,
    promoter_holding_pct     DECIMAL(5,2),
    promoter_pledge_pct      DECIMAL(5,2),
    fii_holding_pct          DECIMAL(5,2),
    dii_holding_pct          DECIMAL(5,2),
    fii_headroom_pct         DECIMAL(5,2),
    is_fii_breached          BOOLEAN DEFAULT FALSE,
    is_fii_cautioned         BOOLEAN DEFAULT FALSE,
    sebi_fine_last_24m       BOOLEAN DEFAULT FALSE,
    sebi_investigation       BOOLEAN DEFAULT FALSE,
    lodr_fine_last_12m       BOOLEAN DEFAULT FALSE,
    business_pivot_count     INTEGER DEFAULT 0,
    shareholding_date        DATE,
    beta_1yr                 DECIMAL(6,4),
    status                   VARCHAR(20) DEFAULT 'active',
    delisted_date            DATE
);

CREATE TABLE price_data (
    symbol             VARCHAR(20),
    date               DATE,
    exchange           VARCHAR(5) DEFAULT 'NSE',  -- 'NSE' or 'BSE' — future BSE expansion
    open               DECIMAL(12,2),
    high               DECIMAL(12,2),
    low                DECIMAL(12,2),
    close              DECIMAL(12,2),
    adj_close          DECIMAL(12,2) NOT NULL,
    adj_factor         DECIMAL(10,6) DEFAULT 1.0,
    volume             BIGINT,
    traded_value_cr    DECIMAL(14,2),
    delivery_qty       BIGINT,
    delivery_pct       DECIMAL(5,2),   -- stored, displayed, NEVER scored
    hit_upper_circuit  BOOLEAN DEFAULT FALSE,
    hit_lower_circuit  BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (symbol, date, exchange)  -- exchange in PK for future BSE rows
);

CREATE TABLE fundamentals (
    id                     SERIAL PRIMARY KEY,
    symbol                 VARCHAR(20),
    period_end_date        DATE,
    reporting_date         DATE NOT NULL,  -- ALWAYS filter by this
    quarter                VARCHAR(10),
    eps                    DECIMAL(10,2),
    eps_growth_yoy         DECIMAL(8,2),
    revenue_cr             DECIMAL(14,2),
    operating_profit_cr    DECIMAL(14,2),
    opm_pct                DECIMAL(6,2),
    net_profit_cr          DECIMAL(14,2),
    other_income_cr        DECIMAL(14,2),
    ocf_cr                 DECIMAL(14,2),
    debt_to_equity         DECIMAL(8,2),
    trade_receivables_days DECIMAL(6,1),
    analyst_revision       DECIMAL(8,2),
    -- analyst_estimate_eps removed v14: Screener.in does not provide this field.
    -- SUE proxy uses eps_growth_yoy instead. Re-add if Trendlyne added as data source.
    expected_result_date   DATE,
    is_financial           BOOLEAN DEFAULT FALSE,
    UNIQUE (symbol, period_end_date)
);

CREATE TABLE indicators (
    symbol          VARCHAR(20),
    date            DATE,
    ma50            DECIMAL(12,2),
    ma150           DECIMAL(12,2),
    ma200           DECIMAL(12,2),
    ma21            DECIMAL(12,2),   -- required for v12 21DMA logic
    ma200_slope     DECIMAL(10,4),
    atr14           DECIMAL(12,2),
    atr20           DECIMAL(12,2),   -- required for v11 50DMA-ATR filter
    rs_rank         INTEGER,
    mom_3m          DECIMAL(8,4),
    mom_6m          DECIMAL(8,4),
    mom_12_1        DECIMAL(8,4),
    raw_score       DECIMAL(8,4),
    scaled_score    DECIMAL(8,4),
    vol_scalar      DECIMAL(6,4),
    mom_vol_20d     DECIMAL(8,4),
    mom_quality     DECIMAL(5,4),
    obv             DECIMAL(20,0),
    adl_ratio       DECIMAL(6,4),
    vol_ratio_20    DECIMAL(6,4),
    vol_ratio_50    DECIMAL(6,4),
    week52_high     DECIMAL(12,2),
    week52_low      DECIMAL(12,2),
    pct_from_high   DECIMAL(6,4),
    delivery_trend  DECIMAL(8,4),   -- display only, never scored
    PRIMARY KEY (symbol, date)
);

-- ─────────────────────────────────────────────
-- REGIME AND MARKET INTERNALS
-- ─────────────────────────────────────────────
CREATE TABLE regime_history (
    date                DATE PRIMARY KEY,
    s1_nifty_vs_ma200   DECIMAL(3,1),
    s2_ma200_slope      DECIMAL(3,1),
    s3_breadth          DECIMAL(3,1),
    s4_highs_lows       DECIMAL(3,1),
    s5_extension        DECIMAL(3,1),
    s6_index_momentum   DECIMAL(3,1),
    regime_score        DECIMAL(4,1),
    crash_warning       BOOLEAN,
    regime_name         VARCHAR(20),
    max_equity_pct      DECIMAL(5,2),
    max_positions       INTEGER,
    risk_per_trade_pct  DECIMAL(4,2),
    distribution_count  INTEGER,
    new_highs_count     INTEGER,
    new_lows_count      INTEGER,
    ad_line_value       DECIMAL(12,2),
    bull_phase          INTEGER,
    fast_crash_active   BOOLEAN DEFAULT FALSE,  -- NEW v13: fast crash detector fired
    fast_crash_5d_return DECIMAL(8,4),          -- NEW v13: rolling 5-day index return at check
    effective_heat_pct  DECIMAL(5,2)            -- NEW v13: regime-dependent heat limit in effect
);

-- ─────────────────────────────────────────────
-- INSTITUTIONAL FLOW
-- ─────────────────────────────────────────────
CREATE TABLE fii_dii_data (
    date           DATE PRIMARY KEY,
    fii_net_buy_cr DECIMAL(14,2),
    dii_net_buy_cr DECIMAL(14,2),
    sector_flows   JSONB
);

CREATE TABLE shareholding_pattern (
    symbol               VARCHAR(20),
    quarter_end_date     DATE,
    promoter_pct         DECIMAL(5,2),
    promoter_pledge_pct  DECIMAL(5,2),
    fii_pct              DECIMAL(5,2),
    dii_pct              DECIMAL(5,2),
    public_pct           DECIMAL(5,2),
    PRIMARY KEY (symbol, quarter_end_date)
);

CREATE TABLE fii_breach_list (
    date              DATE,
    symbol            VARCHAR(20),
    breach_type       VARCHAR(20),
    fii_limit_pct     DECIMAL(5,2),
    current_fii_pct   DECIMAL(5,2),
    PRIMARY KEY (date, symbol)
);

CREATE TABLE bulk_deals (
    id             SERIAL PRIMARY KEY,
    date           DATE,
    symbol         VARCHAR(20),
    client_name    VARCHAR(200),
    deal_type      VARCHAR(10),
    quantity       BIGINT,
    price          DECIMAL(12,2),
    value_cr       DECIMAL(12,2),
    is_institution BOOLEAN DEFAULT FALSE
);

-- ─────────────────────────────────────────────
-- SECTOR RANKINGS (NEW v14)
-- ─────────────────────────────────────────────
CREATE TABLE sector_rankings (
    date            DATE,
    sector          VARCHAR(50),
    rank            INTEGER,           -- 1 = strongest sector
    total_sectors   INTEGER,
    score           DECIMAL(8,4),      -- equal-weighted median 3m momentum of members
    is_top3         BOOLEAN,           -- rank <= 3 → +10 bonus
    is_bottom3      BOOLEAN,           -- rank >= total-2 → -5 penalty
    PRIMARY KEY (date, sector)
);

CREATE INDEX idx_sector_date ON sector_rankings (date DESC, rank);

-- ─────────────────────────────────────────────
-- SIGNALS AND WATCHLIST
-- ─────────────────────────────────────────────
CREATE TABLE signals (
    id                   SERIAL PRIMARY KEY,
    signal_date          DATE,
    symbol               VARCHAR(20),
    pattern_type         VARCHAR(20),
    status               VARCHAR(20),
    pivot_price          DECIMAL(12,2),
    stop_loss            DECIMAL(12,2),
    entry_zone_low       DECIMAL(12,2),
    entry_zone_high      DECIMAL(12,2),
    volume_ratio         DECIMAL(6,4),
    obv_slope            DECIMAL(12,4),
    obv_bonus            INTEGER,
    obv_divergence       BOOLEAN,
    adl_ratio            DECIMAL(6,4),
    delivery_trend       DECIMAL(8,4),
    inst_flow_signal     VARCHAR(20),
    inst_flow_positive   BOOLEAN,
    base_length_days     INTEGER,
    base_depth_pct       DECIMAL(5,2),
    contraction_count    INTEGER,
    regime               VARCHAR(20),
    crash_warning        BOOLEAN,
    earnings_date        DATE,
    days_to_earnings     INTEGER,
    earnings_flag        BOOLEAN,
    tier                 INTEGER,
    composite_score      DECIMAL(8,4),
    vol_scalar           DECIMAL(6,4),
    fundamental_bonus    INTEGER,
    large_cap_warning    BOOLEAN DEFAULT FALSE,
    monster_score        INTEGER DEFAULT 0,
    is_monster_candidate BOOLEAN DEFAULT FALSE,
    sue_yoy_growth_pct    DECIMAL(8,2),              -- v14: eps_growth_yoy at signal date (SUE proxy input)
    sue_bonus_active      BOOLEAN DEFAULT FALSE,     -- v14: within 60-day SUE drift window
    sector_rank_at_signal INTEGER,                   -- v14: sector rank on signal date
    confirmed_date       DATE,
    failed_date          DATE
);

CREATE TABLE watchlist (
    date                 DATE,
    symbol               VARCHAR(20),
    rank                 INTEGER,
    tier                 INTEGER,
    composite_score      DECIMAL(8,4),
    momentum_score       DECIMAL(8,4),
    fundamental_bonus    INTEGER,
    obv_bonus            INTEGER,
    obv_divergence       BOOLEAN,
    adl_ratio            DECIMAL(6,4),
    delivery_trend       DECIMAL(8,4),
    inst_flow_signal     VARCHAR(20),
    inst_flow_positive   BOOLEAN,
    pattern_type         VARCHAR(20),
    signal_id            INTEGER REFERENCES signals(id),
    entry_zone_low       DECIMAL(12,2),
    entry_zone_high      DECIMAL(12,2),
    stop_loss            DECIMAL(12,2),
    suggested_size_pct   DECIMAL(5,2),
    vol_scalar           DECIMAL(6,4),
    earnings_date        DATE,
    earnings_flag        BOOLEAN,
    days_to_earnings     INTEGER,
    regime               VARCHAR(20),
    large_cap_warning    BOOLEAN DEFAULT FALSE,
    monster_score        INTEGER DEFAULT 0,        -- NEW v12
    is_monster_candidate BOOLEAN DEFAULT FALSE,    -- NEW v12
    PRIMARY KEY (date, symbol)
);

-- ─────────────────────────────────────────────
-- PERFORMANCE AND POSITIONS
-- ─────────────────────────────────────────────
CREATE TABLE open_positions (
    id                   SERIAL PRIMARY KEY,
    symbol               VARCHAR(20),
    entry_date             DATE,
    entry_price            DECIMAL(12,2),
    actual_fill            DECIMAL(12,2),
    shares                 INTEGER,
    position_value         DECIMAL(14,2),
    position_pct           DECIMAL(5,2),
    current_stop           DECIMAL(12,2),
    stop_type              VARCHAR(20),
    trailing_pct           DECIMAL(5,2),
    regime_at_entry        VARCHAR(20),
    vol_scalar             DECIMAL(6,4),
    obv_bonus              INTEGER,
    earnings_flagged       BOOLEAN,
    beta_at_entry          DECIMAL(6,4),
    ma21_below_count       INTEGER DEFAULT 0,         -- v11/v12: 21DMA counter
    monster_score          INTEGER DEFAULT 0,         -- v12: score at entry
    is_monster_candidate   BOOLEAN DEFAULT FALSE,     -- v12: score >= threshold
    monster_override_active BOOLEAN DEFAULT FALSE,   -- v13: Phase 4 gain-gated override active
    rs_below_floor_weeks   INTEGER DEFAULT 0,         -- v13: RS persistence counter (weekly)
    atr_at_entry           DECIMAL(12,2),             -- v13: ATR14 at entry for compression check
    fast_crash_reduced     BOOLEAN DEFAULT FALSE,     -- v13: position was halved by fast crash detector
    correlation_adj_applied BOOLEAN DEFAULT FALSE,   -- NEW v14: size was reduced due to correlation
    is_active              BOOLEAN DEFAULT TRUE
);

CREATE TABLE performance_log (
    id                     SERIAL PRIMARY KEY,
    symbol                 VARCHAR(20),
    entry_date             DATE,
    exit_date              DATE,
    entry_price            DECIMAL(12,2),
    actual_fill            DECIMAL(12,2),
    exit_price             DECIMAL(12,2),
    shares                 INTEGER,
    pnl_pct                DECIMAL(8,4),
    pnl_inr                DECIMAL(12,2),
    exit_reason            VARCHAR(50),             -- v13 expanded reason codes
    holding_days           INTEGER,
    max_gain_pct           DECIMAL(8,4),
    max_loss_pct           DECIMAL(8,4),
    pattern_type           VARCHAR(20),
    regime_at_entry        VARCHAR(20),
    vol_scalar_at_entry    DECIMAL(6,4),
    obv_bonus_at_entry     INTEGER,
    earnings_flagged       BOOLEAN,
    days_to_earnings       INTEGER,
    exit_cascade_layer     VARCHAR(20),
    was_manual_reviewed    BOOLEAN DEFAULT FALSE,
    manual_review_outcome  VARCHAR(20),
    algo_signal_only_pnl   DECIMAL(8,4),
    monster_score_at_entry INTEGER DEFAULT 0,
    was_monster_override   BOOLEAN DEFAULT FALSE,    -- v12: Phase 4 applied via override
    monster_override_gain_at_activation DECIMAL(8,4), -- NEW v13: gain% when override activated
    rs_persist_exit        BOOLEAN DEFAULT FALSE,    -- NEW v13: exit was via 4-week RS persistence
    time_stop_suppressed   BOOLEAN DEFAULT FALSE,    -- NEW v13: time stop suppressed due to ATR compression
    fast_crash_affected    BOOLEAN DEFAULT FALSE     -- NEW v13: position was touched by fast crash detector
);

-- ─────────────────────────────────────────────
-- WATCH LISTS AND SPECIAL CATEGORIES
-- ─────────────────────────────────────────────
CREATE TABLE preproft_watchlist (
    symbol               VARCHAR(20) PRIMARY KEY,
    added_date           DATE,
    reason               TEXT,
    revenue_growth_pct   DECIMAL(8,2),
    latest_eps           DECIMAL(10,2),
    profitable_qtrs      INTEGER DEFAULT 0,
    last_checked         DATE,
    promoted_to_universe BOOLEAN DEFAULT FALSE,
    promoted_date        DATE
);

CREATE TABLE large_cap_graduates (
    symbol              VARCHAR(20) PRIMARY KEY,
    graduation_date     DATE,
    mktcap_at_exit      DECIMAL(14,2),
    exit_price          DECIMAL(12,2),
    entry_price         DECIMAL(12,2),
    total_return        DECIMAL(8,4)
);

-- NEW v12: Monster candidate tracking table
CREATE TABLE monster_candidates (
    symbol                  VARCHAR(20),
    date                    DATE,
    monster_score           INTEGER,
    is_monster_candidate    BOOLEAN,
    rs_rank                 INTEGER,
    consolidation_count     INTEGER,
    mom_quality             DECIMAL(5,4),
    sector_rank             INTEGER,
    eps_acc_quarters        INTEGER,
    base_depth_contracting  BOOLEAN,
    composite_score         DECIMAL(8,4),
    tier                    INTEGER,
    notes                   TEXT,
    PRIMARY KEY (symbol, date)
);

-- ─────────────────────────────────────────────
-- BACKTEST RESULTS
-- ─────────────────────────────────────────────
CREATE TABLE backtest_results (
    id              SERIAL PRIMARY KEY,
    test_name       VARCHAR(50),
    test_number     INTEGER,
    variant         VARCHAR(10),
    run_date        TIMESTAMP DEFAULT NOW(),
    period_start    DATE,
    period_end      DATE,
    parameters      JSONB,
    trial_number    INTEGER,
    cagr            DECIMAL(8,4),
    nifty_alpha     DECIMAL(8,4),
    win_rate        DECIMAL(5,4),
    avg_win         DECIMAL(8,4),
    avg_loss        DECIMAL(8,4),
    win_loss_ratio  DECIMAL(6,4),
    expectancy_pct  DECIMAL(8,4),
    max_drawdown    DECIMAL(8,4),
    sharpe_ratio    DECIMAL(8,4),
    calmar_ratio    DECIMAL(8,4),
    deflated_sharpe DECIMAL(8,4),
    pbo_value       DECIMAL(5,4),
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
    id           SERIAL PRIMARY KEY,
    window_type  VARCHAR(20),
    fold         INTEGER,
    train_start  DATE,
    train_end    DATE,
    test_start   DATE,
    test_end     DATE,
    is_sharpe    DECIMAL(8,4),
    oos_sharpe   DECIMAL(8,4),
    oos_is_ratio DECIMAL(8,4),
    is_cagr      DECIMAL(8,4),
    oos_cagr     DECIMAL(8,4),
    passed_gate  BOOLEAN
);

-- ─────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────
CREATE INDEX idx_price_sym_date    ON price_data (symbol, date DESC);
CREATE INDEX idx_price_date        ON price_data (date DESC);
CREATE INDEX idx_ind_date_score    ON indicators (date DESC, scaled_score DESC);
CREATE INDEX idx_fund_sym_rdate    ON fundamentals (symbol, reporting_date DESC);
CREATE INDEX idx_fund_result_date  ON fundamentals (symbol, expected_result_date);
CREATE INDEX idx_sig_date_tier     ON signals (signal_date DESC, tier, status);
CREATE INDEX idx_watch_date        ON watchlist (date DESC, rank);
CREATE INDEX idx_perf_exit         ON performance_log (exit_date DESC);
CREATE INDEX idx_regime_date       ON regime_history (date DESC);
CREATE INDEX idx_bulk_sym_date     ON bulk_deals (symbol, date DESC);
CREATE INDEX idx_monster_date      ON monster_candidates (date DESC, monster_score DESC);
```

---

## 7. Settings File v16.0

```python
# config/settings.py — v16.0
# Only 10 parameters marked [FREE] should be changed during backtest optimisation.
# All others are LOCKED at research-proven values — never change based on backtest.

# ── OOS LOCKOUT (set before any code) ──────────────────────────────
BACKTEST_START = '2010-01-01'
BACKTEST_END   = '2022-12-31'  # 2023–2024 LOCKED as true OOS

# ── Universe [FREE — optimise in Test 2] ────────────────────────────
MARKET_CAP_MIN_CR          = 1000     # [FREE] test 1000 / 1500 / 2000
MARKET_CAP_MAX_CR          = 30000    # LOCKED — graduation exit at ceiling
MIN_DAILY_TRADED_VALUE_CR  = 15   # [FREE] test 10 / 15 / 20 in Test 2
# AUDIT NOTE (March 2026): v7 used ₹15cr (locked). v16 initially set ₹10cr.
# Default corrected to ₹15cr pending Test 2 confirmation.
# Only lower to ₹10cr if Test 2 shows Calmar improves by >5% at ₹10cr.
# See "Known Discrepancies vs v7 — Flaw 3" section for full rationale.
MIN_FREE_FLOAT_PCT         = 20       # LOCKED
MIN_HISTORY_DAYS           = 200      # LOCKED — IPO rule

# ── Momentum weights [FREE — optimise in Test 1] ────────────────────
MOM_WEIGHT_12_1 = 0.40   # [FREE] test 0.30–0.50
MOM_WEIGHT_6M   = 0.35   # [FREE] test 0.25–0.45
MOM_WEIGHT_3M   = 0.25   # [FREE] test 0.15–0.30

# ── Volatility scaling [FREE — optimise in Test 1] ──────────────────
VOL_TARGET_PCT       = 20.0   # [FREE] test 15 / 20 / 25
VOL_SCALAR_MAX       = 2.0    # LOCKED — Barroso & Santa-Clara
PORTFOLIO_VOL_TARGET = 0.15   # LOCKED

# ── Filters ─────────────────────────────────────────────────────────
RS_RANK_MIN_PCT       = 30    # [FREE] test 20/30/40 in Test 1
MOM_QUALITY_MIN       = 0.55  # [FREE] test 0.50/0.55/0.60/remove in Test 1
JUNK_MIN_POS_EPS_QTRS = 2     # LOCKED

# ── Hard block thresholds LOCKED ────────────────────────────────────
PLEDGE_THRESHOLD_OPERATIONAL    = 20  # LOCKED
PLEDGE_THRESHOLD_INFRASTRUCTURE = 50  # LOCKED
BUSINESS_PIVOT_YEARS            = 5   # LOCKED
BUSINESS_PIVOT_MAX              = 3   # LOCKED
OCF_NEG_QUARTERS_HARD_BLOCK     = 3   # LOCKED

# ── Fundamental bonus scores — INITIAL ESTIMATES ────────────────────
BONUS_REV_OPM_SIMUL    = 12   # initial estimate
BONUS_SECTOR_TOP3      = 10   # initial estimate
BONUS_REV_ACCEL_30PCT  = 10   # initial estimate
BONUS_EPS_ACCEL        = 8    # initial estimate
BONUS_OPM_EXPAND_300BP = 8    # initial estimate
BONUS_PROMOTER_BUY     = 8    # initial estimate
BONUS_MKTCAP_CROSS     = 6    # initial estimate
BONUS_EPS_15PCT        = 5    # initial estimate
BONUS_OBV_RISING       = 5    # initial estimate
BONUS_ADL_RATIO        = 4    # initial estimate
BONUS_ANALYST_REV      = 4    # initial estimate
BONUS_EPS_POS          = 2    # initial estimate
BONUS_INST_FLOW        = 1    # initial estimate
BONUS_LOW_DE           = 2    # initial estimate

# ── Penalty scores LOCKED ───────────────────────────────────────────
PENALTY_PROMOTER_SELL       = -8   # LOCKED
PENALTY_SEBI_INVESTIGATION  = -10  # LOCKED
PENALTY_LODR_FINE           = -3   # LOCKED
PENALTY_REV_PROF_DIV        = -5   # LOCKED
PENALTY_OTHER_INCOME        = -5   # LOCKED
PENALTY_OCF_RATIO           = -5   # LOCKED
PENALTY_DEBTORS_120         = -3   # LOCKED
PENALTY_DEBTORS_180         = -5   # LOCKED
PENALTY_HIGH_DE             = -2   # LOCKED
PENALTY_SECTOR_BOT3         = -5   # LOCKED

REV_PROF_DIV_QUARTERS  = 3     # LOCKED
OTHER_INCOME_THRESHOLD = 0.30  # LOCKED
OCF_RATIO_THRESHOLD    = 0.40  # LOCKED
DEBTORS_LOW_DAYS       = 120   # LOCKED
DEBTORS_HIGH_DAYS      = 180   # LOCKED

# ── Beta and float sizing LOCKED ────────────────────────────────────
BETA_HIGH_THRESHOLD     = 2.5   # LOCKED
BETA_SIZE_REDUCTION     = 0.60  # LOCKED
THIN_FLOAT_PROMOTER_PCT = 75    # LOCKED

# ── Entry rules ─────────────────────────────────────────────────────
EARNINGS_SAFETY_DAYS  = 10    # [FREE] test 7/10/14 in Test 6
MAX_ENTRY_ABOVE_PIVOT = 0.03  # LOCKED
VCP_MIN_CONTRACTIONS  = 3     # [FREE] test 2/3/4 in Test 6
VCP_MAX_DEPTH         = 0.40  # [FREE] test 0.30/0.40/0.50 in Test 6
VCP_MIN_WEEKS         = 5     # LOCKED
VCP_MAX_WEEKS         = 52    # LOCKED
VCP_BREAKOUT_VOL      = 1.5   # [FREE] test 1.25/1.5/2.0 in Test 6

# ── Exit rules — v13 FRAMEWORK ──────────────────────────────────────
# Phase 1: Prove-it (0-25% gain)
PHASE1_STOP_PCT = 8.0    # [FREE] test 6/8/10 in Test 7

# Phase 2: Let it run (25-100% gain)
PHASE2_TRAIL_PCT           = 20.0  # [FREE] test 15/20/25 in Test 7
PHASE2_RS_FLOOR            = 30    # LOCKED
PHASE2_REQUIRE_MA50_RISING = True  # LOCKED

# Phase 3: Working compounder (100-200% gain)
PHASE3_TRAIL_PCT = 15.0  # [FREE] test 12/15/18 in Test 7
PHASE3_RS_FLOOR  = 30    # LOCKED

# Phase 4: Monster run (200%+ gain OR monster override — gain-gated at 40%)
PHASE4_USE_10WEEK_MA = True   # LOCKED
PHASE4_TRAIL_PCT     = 12.0   # [FREE] secondary trail
PHASE4_PARTIAL_1     = 0.25   # LOCKED
PHASE4_PARTIAL_2     = 0.25   # LOCKED

# ── v13 NEW: RS persistence filter ──────────────────────────────────
# RS rank must remain below floor for this many consecutive weeks before exit fires.
# Replaces single-day hard exit in Phase 2, Phase 3, Phase 4.
# Exception: RS rank < 20 (total collapse) remains a daily hard exit — no persistence.
RS_PERSIST_WEEKS = 4   # LOCKED — 4 consecutive weeks below floor required

# ── v13 NEW: Time stop ATR compression suppression ──────────────────
# If current ATR14 < atr_at_entry * this ratio, time stop is suppressed.
# A 30%+ compression in daily range = coiling base, not a dead trade.
# Flat price + shrinking ATR = hold. Only suppress if both conditions met
# (holding_days >= TIME_STOP_DAYS AND gain < TIME_STOP_MAX_GAIN).
ATR_COMPRESS_SUPPRESS_RATIO = 0.70  # LOCKED — current ATR must be < 70% of entry ATR

# ── v13 NEW: Monster override gain gate ─────────────────────────────
# Monster override (Phase 4 rules regardless of gain) requires BOTH:
#   monster_score >= MONSTER_SCORE_THRESHOLD  AND  gain >= this value
# Below this gain: monster score is tracked but phase is NOT overridden.
# At or above this gain: Phase 4 exit rules apply regardless of actual gain.
MONSTER_OVERRIDE_MIN_GAIN = 0.40   # LOCKED — 40% gain confirmation required

# ── v13 NEW: Regime-dependent portfolio heat ────────────────────────
# Replaces flat MAX_PORTFOLIO_HEAT = 4.0 from v12.
# Heat limit varies by regime — higher in bull markets where concentration is alpha.
# Used in check_portfolio_constraints() — regime string is passed at call time.
HEAT_STRONG_BULL = 6.0   # LOCKED — Strong Bull: 6% max heat
HEAT_BULL        = 5.0   # LOCKED — Bull: 5% max heat
HEAT_WEAK        = 4.0   # LOCKED — Weak: 4% max heat (same as old flat value)
HEAT_BEAR        = 2.0   # LOCKED — Bear: 2% max heat
# Full Bear: 0% heat — no new positions, all heat from existing positions winds down
# MAX_PORTFOLIO_HEAT retained as fallback default if regime string is unrecognised
MAX_PORTFOLIO_HEAT = 4.0  # LOCKED — fallback only, not primary in v13

# ── v13 NEW: Fast crash detector ────────────────────────────────────
# Fires if market index drops more than FAST_CRASH_PCT in FAST_CRASH_DAYS trading days.
# Independent of and faster than the 6-signal regime engine.
# Response: halve all open position sizes, block all new entries.
# Validated: March 2020 Nifty 50 lost ~12% in first 5 trading days of crash.
# Fast detector fires immediately. Regime engine needed until Mar 12–16.
FAST_CRASH_PCT  = 0.08  # LOCKED — 8% decline threshold
FAST_CRASH_DAYS = 5     # LOCKED — rolling 5-trading-day window
# Reset condition: no rolling 5-day window in last 10 days shows decline > 8%

# ── v12 retained: 21DMA volume direction thresholds ─────────────────
PULLBACK_LOW_VOL_THRESHOLD  = 0.75  # LOCKED — below this = hold override (dry-up)
PULLBACK_HIGH_VOL_THRESHOLD = 1.50  # LOCKED — above this = instant distribution confirm

# ── v12 retained: Trend integrity check ─────────────────────────────
TREND_INTEGRITY_LOOKBACK = 20  # LOCKED — trading days for swing high/low detection

# ── 21DMA confirmation parameters ───────────────────────────────────
MA21_CONFIRM_DAYS = 3    # [FREE] test 2/3/4
MA21_VOL_MULT     = 1.5  # [FREE] test 1.25/1.5/2.0
ATR_MULT_50DMA    = 1.5  # [FREE] test 1.0/1.5/2.0

# ── Climax run ───────────────────────────────────────────────────────
CLIMAX_SELL_PCT       = 0.50   # LOCKED — 50% sell on climax (increased from 25% in v11)
CLIMAX_WINDOW_GAIN    = 0.30   # LOCKED
CLIMAX_WINDOW_DAYS    = 15     # LOCKED
CLIMAX_MIN_PRIOR_GAIN = 1.00   # LOCKED — Phase 3/4 only (100%+ gain required)

# ── Time stop ────────────────────────────────────────────────────────
# v13: time stop now suppressed if ATR is compressing (see ATR_COMPRESS_SUPPRESS_RATIO)
TIME_STOP_DAYS     = 20    # LOCKED
TIME_STOP_MAX_GAIN = 0.05  # LOCKED

# ── Mandatory overrides ──────────────────────────────────────────────
MA200_BREACH_DAYS = 3   # LOCKED — exit within 3 days of weekly MA200 breach

# ── Exit cascade thresholds LOCKED ──────────────────────────────────
DIST_DAY_ALERT    = 4   # LOCKED
DIST_DAY_REDUCE   = 5   # LOCKED
DIST_DAY_DANGER   = 6   # LOCKED
NEW_HIGHS_TIGHTEN = 50  # LOCKED
NEW_HIGHS_REDUCE  = 20  # LOCKED
AD_DIV_WEEKS      = 3   # LOCKED

# ── Monster Stock Detection (v12 + v13 additions) ───────────────────
# Evidence: Bessembinder 2018 — top 4% of stocks drive all net wealth creation
# Framework: John Boik — common profile of monster stocks before major runs
MONSTER_SCORE_THRESHOLD = 80   # LOCKED — score >= 80 qualifies as monster candidate

# Monster score component weights (LOCKED — initial estimates, validate in Test 5)
MONSTER_RS_RANK_BONUS          = 25  # RS rank >= 90th percentile
MONSTER_CONSOLIDATION_BONUS    = 20  # 3+ prior consolidations
MONSTER_MOM_QUALITY_BONUS      = 20  # mom_quality >= 0.70
MONSTER_SECTOR_RANK_BONUS      = 15  # sector rank #1
MONSTER_EPS_ACCEL_BONUS        = 10  # 4+ consecutive quarters EPS acceleration
MONSTER_BASE_DEPTH_BONUS       = 10  # base depths contracting across consolidations
MONSTER_SECTOR_OUTPERFORM_BONUS = 10 # NEW v13: outperforms sector index 2× over 6m
MONSTER_MAX_SCORE              = 100 # cap — additional criteria cannot push above 100

# Thresholds for individual monster criteria (LOCKED)
MONSTER_RS_RANK_MIN            = 90   # minimum RS rank percentile for RS bonus
MONSTER_MOM_QUALITY_MIN        = 0.70 # minimum mom_quality for quality bonus
MONSTER_CONSOL_MIN_COUNT       = 3    # minimum prior consolidations for bonus
MONSTER_EPS_ACCEL_QTRS         = 4    # consecutive quarters of acceleration required
MONSTER_PANEL_THRESHOLD        = 60   # show in candidates panel (below override threshold)
MONSTER_SECTOR_OUTPERFORM_MULT = 2.0  # NEW v13: stock must return 2× sector return (6m)
                                       # scoring bonus only — not a hard gate

# ── Position sizing ──────────────────────────────────────────────────
# Set based on Test 10 win rate result:
#   win rate < 45%:   use 1.0%
#   win rate 45-55%:  use 1.5%
#   win rate > 55%:   use 2.0%
RISK_PER_TRADE_PCT = 1.0   # [UPDATE after Test 10]
MAX_POSITION_PCT   = 20.0  # LOCKED
MIN_POSITION_PCT   = 2.0   # LOCKED
MAX_SECTOR_CONC    = 30.0  # LOCKED

# ── Drawdown circuit breaker LOCKED ─────────────────────────────────
DRAWDOWN_HALVE_PCT = 10.0  # LOCKED
DRAWDOWN_CASH_PCT  = 20.0  # LOCKED

# ── Rebalancing [FREE — optimise in Test 8] ─────────────────────────
REBALANCE_FREQ = 'monthly'  # [FREE] test weekly/monthly/semi-annual
RS_EXIT_THRESH = 30         # LOCKED

# ── v14 NEW: Correlation-aware position sizing ──────────────────────
# Reduces position size when new stock correlates highly with existing holdings.
# Measured on daily adj_close returns over prior 60 trading days.
# Minimum 30 overlapping days required — if fewer, no adjustment applied.
CORR_HIGH_THRESHOLD     = 0.85   # LOCKED — above this = 50% size reduction
CORR_MED_THRESHOLD      = 0.70   # LOCKED — above this = 25% size reduction
CORR_SIZE_HIGH_REDUCTION = 0.50  # LOCKED — keep 50% of base shares
CORR_SIZE_MED_REDUCTION  = 0.75  # LOCKED — keep 75% of base shares
CORR_LOOKBACK_DAYS       = 60    # LOCKED — return window for correlation calculation
CORR_MIN_OVERLAP_DAYS    = 30    # LOCKED — minimum common days required

# ── v14: SUE proxy bonus (post-earnings drift) ──────────────────────
# Bernard & Thomas 1989 + Chan, Jegadeesh & Lakonishok 1996.
# Uses eps_growth_yoy (Screener.in, 100% universe coverage).
# NO analyst estimates required — SUE proxy via YoY EPS growth rate.
# Thresholds are YoY EPS growth % (not analyst beat/miss %).
#
# PEAD_ENABLED: set False to disable entirely during backtest testing
# or if live validation shows signal adds noise rather than alpha.
# Test 5 and Test 9 will confirm whether it adds OOS Sharpe.
# Default True — run enabled, validate in Test 5.
PEAD_ENABLED      = True   # set False if live validation shows noise
PEAD_DRIFT_DAYS   = 60     # LOCKED — drift window in trading days
PEAD_BONUS_LARGE  = 10     # LOCKED — eps_growth_yoy > 50%: +10
PEAD_BONUS_SMALL  = 6      # LOCKED — eps_growth_yoy > 25%: +6
PEAD_PENALTY      = -8     # LOCKED — eps_growth_yoy < -20%: -8
# Thresholds are higher than analyst-based PEAD because YoY growth
# is a coarser signal — only very large moves are meaningful surprises.

# ── v14 NEW: Sector ranking ──────────────────────────────────────────
# calculate_sector_rankings() uses 63-day lookback (= mom_3m).
# Rankings updated daily in sector_rankings table.
# Feeds sector bonus/penalty in build_composite_score().
SECTOR_RANK_LOOKBACK = 63  # LOCKED — 63 trading days = 3 months

# ── v14 NEW: Monthly rebalancing logic ──────────────────────────────
# Used in monthly_rebalance() (UC-08B).
# REBALANCE_SWAP_FLAG_THRESHOLD: challenger must beat incumbent by this
# many composite score points before a manual review flag is raised.
# Never auto-swap — human confirms all position swaps.
REBALANCE_SWAP_FLAG_THRESHOLD = 15  # LOCKED — score gap required for flag

# ── v14 NEW: Adversarial walk-forward (Fold 8) ──────────────────────
# Training set: non-bull calendar years only.
# Test set: 2019 bull recovery.
FOLD8_TRAIN_YEARS     = [2015, 2016, 2018, 2022]  # LOCKED
FOLD8_TEST_YEAR       = 2019                       # LOCKED
FOLD8_MIN_OOS_SHARPE_RATIO = 0.50  # LOCKED — must be >= 50% of Folds 1-4 average

# ── v16 NEW: Earnings Turnaround Watch ──────────────────────────────
# Monitoring-only alert for stocks transitioning from loss to profit.
# Does NOT change entry rules. Hard blocks still apply at all times.
# Gives 1–3 quarter advance warning before Tier 1/2 signal fires.
#
# Validated: GE Vernova T&D — watch fires at ₹220 (Jun 2023),
# entry at ₹280-320 (Sep-Oct 2023) vs ₹350-380 without this feature.
# Zero false entries across all 40 validation stocks.
#
# Set TURNAROUND_ALERT_ENABLED = False to disable entirely if
# panel creates noise or psychological override temptation.
TURNAROUND_ALERT_ENABLED       = True    # set False to disable panel
TURNAROUND_HISTORY_QTRS        = 2       # LOCKED — min loss quarters required
TURNAROUND_EPS_IMPROVEMENT_QTRS = 4     # LOCKED — monotone improvement quarters
TURNAROUND_MIN_REVENUE_GROWTH  = 0.10   # LOCKED — min 10% YoY revenue growth

# ── Pipeline timing LOCKED ──────────────────────────────────────────
PIPELINE_TRIGGER = '16:15'  # LOCKED
ALERT_TARGET     = '17:00'  # LOCKED
```

---

## 8. Implementation Timeline

| Phase | Week | Task | Gate |
|---|---|---|---|
| 0 | NOW — TODAY | Lock 2023–2024 OOS: `BACKTEST_END = '2022-12-31'` | CRITICAL — before any code |
| 0 | Week 1 | Download 10yr NSE data (2015–2022 only). ALL delisted stocks included. | Data quality audit passes |
| 0 | Week 1–2 | Calculate adj_close for all corporate actions. Verify 10 known events manually. | adj_close verified |
| 0 | Week 2 | Update settings.py to v14.0 spec. Lock all non-free parameters. | Settings.py matches v14.0 |
| 1 | Week 3–4 | Build regime engine (UC-03) + exit cascade (UC-03B) + bull entry (UC-03C) | Fires March 2020 Bear, July 2020 Bull |
| 1 | Week 4–5 | Build all indicators including OBV, MA21, ATR20 (base-period scope fix confirmed) | Unit tests pass |
| 1 | Week 5–6 | Build universe filters: all 8 hard blocks including pledge split, pivot rule, OCF | Every hard block verified |
| 1 | Week 6–7 | Build scoring engine: all bonuses and penalties including new v8 signals | Spot-check 20 stocks |
| 1 | Week 7–8 | Build VCP detection + Stage 2 template + entry rules + false breakout filter | Pattern detection unit tests (Fix P9) |
| 1 | Week 8–9 | Build exit engine: phase-based exits + v12 volume pullback + trend integrity + v13 RS persistence + ATR compression + gain-gated monster override | Exit logic verified |
| 1 | Week 9 | Build all helper functions: `calculate_monster_score()`, `check_trend_integrity()`, `classify_pullback_volume()`, `check_atr_compressing()`, `check_rs_persistence()`, `check_fast_crash()`, `calculate_correlation_adjusted_size()`, `calculate_sue_proxy_bonus()`, `calculate_sector_rankings()`, `monthly_rebalance()` | All 10 functions unit tested |
| 2 | Week 9–11 | Backtest Tests 1–5 | Component gates 1–5 pass |
| 2 | Week 11–13 | Backtest Tests 6–9 | Component gates 6–9 pass |
| 2 | Week 13–15 | Backtest Test 10 (full system, 2015–2022) | All 6 hard gates pass |
| 2 | Week 15–16 | Walk-forward: 4 expanding + 3 rolling folds | OOS Sharpe ≥70% IS all folds |
| 2 | Week 16 | Tests 11–13: null hypothesis, DSR, PBO | p<0.05, DSR>0.95, PBO<30% |
| 2 | Week 17 | Test 14: Reveal OOS 2023–2024. Zero parameter changes. | If fails: back to design. No shortcuts. |
| 2 | Week 17–18 | Tests 15–16: cost sensitivity, capacity test | Edge survives all scenarios |
| 3 | Week 18–19 | Streamlit dashboard + monster candidates panel + daily pipeline automation | Pipeline running 2 weeks clean |
| 3 | Week 19–43 | Paper trading — 6 months minimum | All paper trading gates pass |
| 4 | Week 43 | Go live — 10% capital (NOT 25%) | All 25 gates checked |
| 4 | Week 43–55 | Monitor live vs paper. Scale to 25% only after correlation >0.90 | 3 months live data |
| 5 | Month 12+ | FastAPI + PostgreSQL + subscription tiers (after SEBI RA registration) | SEBI RA prerequisite |
| 5 | Month 18+ | Zerodha Kite Connect auto-execution for personal account | 6 months live validated first |
| 6 | Month 24+ | Client auto-execution (PMS/IA licence required, not just RA) | Separate SEBI licence |

---

## 9. 40-Stock Validation Reference

Zero false entries into genuine traps. Zero missed catches on eligible stocks.

**Master Scorecard**

| Category | Count | Examples |
|---|---|---|
| Main system clean catches | 13 | Deepak Nitrite, Alkyl Amines, Himadri, GPIL, Mazagon Dock, GE Vernova, Lloyds Metals, Force Motors, Cochin Shipyard, Hitachi Energy India, JBM Auto, Shakti Pumps, KPI Green |
| Satellite catches (main missed) | 8 | PGEL, Cupid, V2 Retail, Tanla, Waaree Renewable, Kernex, Apollo Micro, Moschip |
| Correctly avoided — traps | 10 | Cosmo Ferrites, Websol, Megasoft, RIR Power, Servotech, Focus Lighting, E2E Networks, Mercury EV-Tech, Magellanic Cloud, SPEL Semiconductor |
| Correctly avoided — IPO rule | 3 | Waaree Energies, NIBE, Mazagon Dock (first 200 days) |
| Graduated out — large cap | 1 | Hitachi Energy India (₹1,11,550cr) |
| Pre-profit watch list | 1 | E2E Networks (68% revenue growth, loss-making) |

**Every Filter Validated by a Named Stock**

| Filter | Validated By | What It Prevented |
|---|---|---|
| ₹1,000cr floor + ₹15cr liquidity (audit-corrected) | Servotech, Danlaw, Cosmo Ferrites | Nano-cap gambling |
| EPS positive 2 of 4 quarters | Megasoft, Websol, E2E Networks | Loss-making narrative stocks |
| Pledge hard block (operational) | Websol (88.1%) | Pledge collapse trap |
| Pledge infrastructure exception | Apollo Micro (34.2%), KPI Green (44.7%) | Unnecessary miss of genuine growth |
| SEBI fine hard block | Megasoft (fine confirmed) | Regulatory fraud risk |
| SEBI investigation penalty | Kernex, Force Motors | Reduced sizing on investigation stocks |
| Business pivot rule | Servotech (4 pivots), Magellanic Cloud, Mercury EV-Tech | Management conviction zero |
| OCF hard block | SPEL Semiconductor (factory shut) | Factory shutdown not earnings |
| Revenue × OPM +12 | Lloyds Metals, Tanla entry, Arrow Greentech | Correctly ranked highest quality |
| OPM expansion +8 | Himadri Chemical, Xpro India | Caught margin expansion stories |
| Revenue/profit divergence −5 | Kernex, Shakti Pumps, MIC Electronics | Earlier warning than MA200 |
| Other income penalty −5 | Megasoft Q1 FY26, Force Motors | Fake EPS signal blocked |
| OCF quality penalty −5 | Tanla exit, IZMO | Earlier exit by 1–2 quarters |
| Promoter selling −8 | Focus Lighting, RIR Power, Shakti Pumps | Distribution trap |
| IPO 200-day rule | NIBE, Waaree Energies | Listing-day volatility trap |
| MA200 breach exit | Tanla, Xpro, GPIL, JBM Auto, Apollo Micro, Olectra | Gains protected before collapse |
| Exit cascade E1 climax | Himadri Oct 2021, GPIL Sept 2021 | Earlier exit than MA200 alone |
| Large-cap graduation | Hitachi Energy India | Clean exit at ₹30,000cr ceiling |
| Beta sizing reduction | Moschip (3.15), Lloyds Metals (2.18) | Oversizing volatile stocks |
| Thin float rule | Diamond Power Infrastructure (84% private promoter) | Thin float extreme volatility |
| Plant disaster rule | Kwality Pharma (fire, MA200 held) | Premature exit on one-time event |

---

## Summary

**UniPro AI — MomentumEdge Use Case v16.0**
**Complete Institutional Operating System**

40 use cases | 5 simulation results | 27+ database tables | 16 backtest tests + adversarial Fold 8 + Test 7H | BSE cross-validation | Full SEBI RA + AIF/PMS compliance stack | GE Vernova T&D 2020–2024 validated

Backtest: 2010–2022 | OOS locked: 2023–2024 | 40-stock logic validated | Exit framework simulation validated | NSE sector classification locked | BSE expansion schema ready | Build once, activate by phase

**Evidence base (16 citations — Novy-Marx 2015 dropped with explanation):**
Jegadeesh & Titman 1993 | Barroso & Santa-Clara 2015 | Dierkes & Krupski 2022 | Granville 1963 | He & Narayanamoorthy 2017 | Grinblatt & Moskowitz 2004 | AQR QMJ | López de Prado 2014 | Lakonishok & Lee 2001 | Chan, Jegadeesh & Lakonishok 1996 | Bernard & Thomas 1989 | Lesmond, Schill & Zhou 2004 | Bailey et al. 2014 | Bessembinder 2018 | Moskowitz & Grinblatt 1999 | Novy-Marx 2015 (superseded — see Evidence Base section)

**v16 addition (7 targeted fixes — 1 enhancement + 3 quality + 3 discipline):**
1. `check_earnings_turnaround()` + `run_turnaround_watch_scan()` — UC-04 Step 0B. Turnaround Watch panel. Pipeline step 12a. Validated: GE Vernova T&D entry ₹350→₹280–₹320. Zero false entries across all 40 stocks.
2. `suppression_reason` + `consecutive_pos_eps` added to `turnaround_watch` table — audit trail clarity + EPS regression detection.
3. Fast crash vs monster override conflict resolved — UC-03D: crash halves all positions including monster cores; `monster_override_active` NOT cleared; Phase 4 resumes on reset.
4. Pre-trade block in UC-34 `place_order()` — technically enforces Turnaround Watch monitoring-only discipline. Blocked attempts logged in `blocked_order_attempts` table (immutable, SEBI audit).
5. `blocked_order_attempts` table added to schema.
6. `TURNAROUND_ALERT_ENABLED`, `TURNAROUND_HISTORY_QTRS`, `TURNAROUND_EPS_IMPROVEMENT_QTRS`, `TURNAROUND_MIN_REVENUE_GROWTH` in settings.
7. Option B (corporate restructuring promoter selling exception) documented as v17 candidate — deferred pending live candidate.

**v15 additions (23 new use cases — full institutional stack):**
Reporting: UC-18–22 | Client management: UC-23–26 | Compliance: UC-27–30 | Fund ops: UC-31–33 | Execution: UC-34–35 | Tech ops: UC-36–38 | BI: UC-39–40

**v14 additions (7 fixes):**
NSE sector classification | BSE cross-validation | `calculate_sector_rankings()` | `calculate_sue_proxy_bonus()` | `calculate_correlation_adjusted_size()` + Test 7H | `monthly_rebalance()` | Walk-forward Fold 8

**v13 additions (6 fixes):** RS persistence | Monster gain gate | ATR compression | Regime heat | Fast crash | Monster sector outperformance

**v12 additions (4 features):** Volume pullback | Trend integrity | Bessembinder | Monster score

---
*Phase 1 (now): UC-01 to UC-17 + UC-36 + UC-37 + UC-18 + UC-19*
*Phase 2 (SEBI RA): UC-23 to UC-30 + UC-20*
*Phase 3 (go-live): UC-34 + UC-35 + UC-38 + UC-39 + UC-40 + UC-21*
*Phase 4 (SaaS): UC-24*
*Phase 5 (AIF/PMS): UC-31 + UC-32 + UC-33 + UC-22*

*v17 candidate: Option B — corporate restructuring promoter selling exception (−3 instead of −8). Reserve until live trading surfaces a clear candidate.*

*SEBI compliance: do not charge clients until RA registration is active. Engage SEBI specialist lawyer before Phase 2.*
