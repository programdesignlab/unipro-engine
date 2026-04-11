"""Pipeline orchestrator — YAML-driven strategy engine.

Loads strategy config from YAML, passes params to each module.
Tags all outputs with strategy_hash for versioned reproducibility.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.core.strategy import StrategyConfig, load_strategy
from momentum_edge.utils.date_utils import prev_trading_day

# Default strategy path (relative to project root)
_DEFAULT_STRATEGY = Path(__file__).parent.parent.parent.parent / "strategies" / "momentum_edge.yaml"


@contextmanager
def _log_step(db: Session, target_date: date, phase: str, strategy_hash: str = ""):
    """Context manager to log pipeline step timing and status."""
    start = time.monotonic()
    try:
        yield
        duration = time.monotonic() - start
        _persist_log(db, target_date, phase, "complete", strategy_hash, duration)
    except Exception as e:
        duration = time.monotonic() - start
        _persist_log(db, target_date, phase, "failed", strategy_hash, duration, str(e))
        raise


def _persist_log(
    db: Session, target_date: date, phase: str, status: str,
    strategy_hash: str, duration: float, error: str | None = None,
) -> None:
    """Write pipeline log entry (silently skip if table doesn't exist)."""
    try:
        db.execute(
            text("""
                INSERT INTO pipeline_log (date, phase, status, strategy_hash, duration_seconds, error_message, completed_at)
                VALUES (:d, :phase, :status, :hash, :dur, :err, :now)
                ON CONFLICT (date, phase) DO UPDATE SET
                    status = EXCLUDED.status,
                    duration_seconds = EXCLUDED.duration_seconds,
                    error_message = EXCLUDED.error_message,
                    completed_at = EXCLUDED.completed_at
            """),
            {"d": target_date, "phase": phase, "status": status, "hash": strategy_hash,
             "dur": round(duration, 2), "err": error, "now": datetime.utcnow()},
        )
    except Exception:
        db.rollback()


def _update_beta_and_psu(db: Session, target_date: date) -> None:
    """Calculate 1yr beta vs Nifty for all stocks and detect PSU stocks."""
    import numpy as np

    # Get Nifty returns
    nifty_stock = db.execute(
        text("SELECT id FROM stocks WHERE symbol IN ('NIFTY 50', '^NSEI', 'NIFTY50') LIMIT 1")
    ).fetchone()

    if not nifty_stock:
        return

    nifty_prices = db.execute(
        text("""
            SELECT date, adj_close FROM eod_prices
            WHERE stock_id = :sid AND date <= :d
            ORDER BY date DESC LIMIT 252
        """),
        {"sid": nifty_stock[0], "d": target_date},
    ).fetchall()

    if len(nifty_prices) < 60:
        return

    nifty_returns = {}
    nifty_list = list(reversed(nifty_prices))
    for i in range(1, len(nifty_list)):
        if nifty_list[i][1] and nifty_list[i - 1][1] and nifty_list[i - 1][1] > 0:
            nifty_returns[nifty_list[i][0]] = (nifty_list[i][1] - nifty_list[i - 1][1]) / nifty_list[i - 1][1]

    # Beta for each stock
    stocks = db.execute(text("SELECT id, symbol FROM stocks WHERE is_active = true")).fetchall()
    updated = 0
    for stock_id, symbol in stocks:
        prices = db.execute(
            text("""
                SELECT date, adj_close FROM eod_prices
                WHERE stock_id = :sid AND date <= :d AND adj_close IS NOT NULL
                ORDER BY date DESC LIMIT 252
            """),
            {"sid": stock_id, "d": target_date},
        ).fetchall()

        if len(prices) < 60:
            continue

        price_list = list(reversed(prices))
        stock_rets = []
        market_rets = []
        for i in range(1, len(price_list)):
            dt = price_list[i][0]
            if dt in nifty_returns and price_list[i - 1][1] and price_list[i - 1][1] > 0:
                sr = (price_list[i][1] - price_list[i - 1][1]) / price_list[i - 1][1]
                stock_rets.append(sr)
                market_rets.append(nifty_returns[dt])

        if len(stock_rets) < 30:
            continue

        market_arr = np.array(market_rets)
        stock_arr = np.array(stock_rets)
        market_var = np.var(market_arr)
        if market_var > 0:
            beta = round(float(np.cov(stock_arr, market_arr)[0, 1] / market_var), 2)
            db.execute(
                text("UPDATE stocks SET beta = :beta WHERE id = :sid"),
                {"beta": beta, "sid": stock_id},
            )
            updated += 1

    # PSU detection: promoter name containing "Government" / "President of India"
    db.execute(text("""
        UPDATE stocks SET is_psu = true
        WHERE id IN (
            SELECT DISTINCT s.id FROM stocks s
            JOIN shareholding_pattern sp ON sp.stock_id = s.id
            WHERE s.promoter_holding_pct > 50
        ) AND (
            sector ILIKE '%public sector%' OR sector ILIKE '%psu%'
            OR name ILIKE '%government%' OR name ILIKE '%india ltd%'
        )
    """))

    db.commit()
    if updated:
        logger.info(f"[Beta/PSU] Updated beta for {updated} stocks")


def _update_open_positions(
    db: Session, target_date: date, regime: str, crash_warning: bool, strategy: StrategyConfig,
) -> None:
    """Update open positions: prices, gain phase, monster score, exit checks, cascade."""
    from momentum_edge.db.models import OpenPosition, Signal
    from momentum_edge.engine.exits import check_exits, determine_phase
    from momentum_edge.engine.exit_cascade import evaluate_cascade
    from momentum_edge.engine.monster import calculate_monster_score

    # 1. Create positions from newly confirmed signals
    confirmed = (
        db.query(Signal)
        .filter(Signal.status == "Confirmed", Signal.confirmed_date == target_date)
        .all()
    )
    for sig in confirmed:
        # Check if position already exists
        existing = db.execute(
            text("SELECT 1 FROM open_positions WHERE stock_id = :sid AND is_active = true"),
            {"sid": sig.stock_id},
        ).fetchone()
        if existing:
            continue

        stock = db.execute(
            text("SELECT symbol, sector FROM stocks WHERE id = :sid"),
            {"sid": sig.stock_id},
        ).fetchone()
        if not stock:
            continue

        db.execute(
            text("""
                INSERT INTO open_positions (
                    stock_id, symbol, sector, entry_date, entry_price, shares,
                    current_stop, gain_phase, entry_regime, entry_composite_score,
                    signal_id, pattern_type, tier, strategy_hash
                ) VALUES (
                    :sid, :sym, :sector, :date, :price, :shares,
                    :stop, 'prove_it', :regime, :score,
                    :signal_id, :pattern, :tier, :hash
                ) ON CONFLICT (stock_id, entry_date) DO NOTHING
            """),
            {
                "sid": sig.stock_id, "sym": stock[0], "sector": stock[1],
                "date": target_date, "price": sig.pivot_price or 0,
                "shares": 0,  # populated by position sizing at order time
                "stop": sig.stop_loss, "regime": regime,
                "score": sig.composite_score, "signal_id": sig.id,
                "pattern": sig.pattern_type, "tier": sig.tier,
                "hash": strategy.strategy_hash,
            },
        )

    # 2. Update all active positions with current prices
    positions = db.execute(
        text("""
            SELECT op.id, op.stock_id, op.symbol, op.entry_price, op.entry_date,
                   op.current_stop, op.rs_below_floor_weeks, op.partial_exits_taken,
                   op.monster_override_active, op.entry_atr,
                   e.adj_close, e.low, e.high
            FROM open_positions op
            LEFT JOIN eod_prices e ON e.stock_id = op.stock_id AND e.date = :d
            WHERE op.is_active = true
        """),
        {"d": target_date},
    ).fetchall()

    if not positions:
        return

    for pos in positions:
        pos_id, stock_id, symbol = pos[0], pos[1], pos[2]
        entry_price, entry_date = pos[3], pos[4]
        adj_close = pos[10]

        if adj_close is None:
            continue

        gain_pct = (adj_close - entry_price) / entry_price if entry_price > 0 else 0
        phase = determine_phase(gain_pct, pos[8])  # monster_override_active
        holding_days = (target_date - entry_date).days if entry_date else 0

        # Monster score
        monster_result = calculate_monster_score(
            db, stock_id, symbol, target_date,
            gain_pct=gain_pct, config=strategy.monster,
        )

        db.execute(
            text("""
                UPDATE open_positions SET
                    current_price = :price, gain_pct = :gain,
                    max_gain_pct = GREATEST(COALESCE(max_gain_pct, 0), :gain),
                    holding_days = :days, gain_phase = :phase,
                    monster_score = :mscore, monster_override_active = :mactive,
                    updated_at = now()
                WHERE id = :id
            """),
            {
                "price": adj_close, "gain": round(gain_pct, 4),
                "days": holding_days, "phase": phase.value,
                "mscore": monster_result.score,
                "mactive": monster_result.override_active,
                "id": pos_id,
            },
        )

    # 3. Run exit engine on active positions
    active_positions = (
        db.query(OpenPosition).filter(OpenPosition.is_active.is_(True)).all()
    )
    if active_positions:
        exit_signals = check_exits(
            db, active_positions, target_date, regime, crash_warning, strategy=strategy,
        )
        for sig in exit_signals:
            if sig.action == "full_exit" or sig.exit_pct >= 1.0:
                db.execute(
                    text("""
                        UPDATE open_positions SET
                            is_active = false, closed_date = :d,
                            exit_reason = :reason, exit_phase = :phase,
                            exit_rule_name = :rule, updated_at = now()
                        WHERE stock_id = :sid AND is_active = true
                    """),
                    {"d": target_date, "reason": sig.exit_type, "phase": sig.phase, "rule": sig.rule_name, "sid": sig.stock_id},
                )
            elif sig.action == "move_stop" and sig.new_stop:
                db.execute(
                    text("UPDATE open_positions SET current_stop = :stop, updated_at = now() WHERE stock_id = :sid AND is_active = true"),
                    {"stop": sig.new_stop, "sid": sig.stock_id},
                )

        # 4. Run cascade
        cascade_actions = evaluate_cascade(
            db, active_positions, target_date, strategy.exits.cascade,
        )
        for action in cascade_actions:
            logger.info(f"[Cascade] {action.layer}: {action.action} — {action.reason}")

    db.commit()
    logger.info(f"[Positions] {len(active_positions)} active, {len(confirmed)} new from signals")


def run_m1(db: Session, target_date: date) -> None:
    """Run Module 1: data ingestion (prices + delivery + FII/DII + deals + surveillance)."""
    from momentum_edge.data.prices import ingest_daily_prices
    from momentum_edge.data.nse_indices import fetch_nifty50_close
    from momentum_edge.data.delivery import ingest_daily_delivery
    from momentum_edge.data.fii_dii import ingest_fii_dii
    from momentum_edge.data.bulk_deals import ingest_bulk_deals
    from momentum_edge.data.surveillance import sync_surveillance

    logger.info(f"[M1] Data ingestion for {target_date}")
    count = ingest_daily_prices(db, target_date)
    logger.info(f"[M1] Prices: {count} stocks written")

    delivery = ingest_daily_delivery(db, target_date)
    logger.info(f"[M1] Delivery: {delivery} stocks written")

    close = fetch_nifty50_close(target_date)
    if close:
        logger.info(f"[M1] Nifty 50 close: {close:.2f}")
    else:
        logger.warning("[M1] Nifty 50 close not available for this date")

    ingest_fii_dii(db, target_date)
    deals = ingest_bulk_deals(db, target_date)
    logger.info(f"[M1] Bulk/block deals: {deals}")

    asm, esm = sync_surveillance(db)
    if asm or esm:
        logger.info(f"[M1] ASM: {asm}, ESM: {esm}")


def run_indicators(db: Session, target_date: date, strategy: StrategyConfig) -> int:
    """Compute and store technical indicators for all stocks."""
    from momentum_edge.scanner.indicators import compute_and_store_indicators

    logger.info(f"[Indicators] Computing for {target_date}")
    count = compute_and_store_indicators(db, target_date, strategy=strategy)
    logger.info(f"[Indicators] {count} stocks computed")
    return count


def run_pipeline(
    db: Session,
    target_date: date | None = None,
    strategy_path: str | Path | None = None,
) -> None:
    """Run the full pipeline for target_date using strategy config from YAML.

    Flow:
    1. M1: Data ingestion (prices, delivery, FII/DII, deals, surveillance)
    2. Indicators: MA, momentum, OBV, A/D, vol scaling, RS rank
    3. M2: Market regime (6 signals + crash indicator)
    4. M3: Sector rotation ranking
    5. Universe filter: hard blocks from strategy YAML
    6. Per stock: fundamental bonus, trend template, breakout, accumulation, composite
    7. M10: Watchlist generation
    """
    from momentum_edge.db.models import Stock
    from momentum_edge.scanner.market_regime import classify_regime
    from momentum_edge.scanner.sector_rotation import rank_sectors, get_sector_score
    from momentum_edge.scanner.trend_template import passes_trend_template
    from momentum_edge.scanner.breakout_patterns import detect_pattern
    from momentum_edge.ranking.universe_filter import passes_hard_filters
    from momentum_edge.ranking.fundamental_bonus import calculate_fundamental_bonus
    from momentum_edge.ranking.accumulation_score import score_accumulation
    from momentum_edge.core.composite import compute_composite
    from momentum_edge.ranking.watchlist import generate_watchlist

    # Load strategy
    strategy = load_strategy(strategy_path or _DEFAULT_STRATEGY)
    strategy_hash = strategy.strategy_hash
    logger.info(
        f"=== MomentumEdge Pipeline — {strategy.meta.name} v{strategy.meta.version} "
        f"[{strategy_hash}] ==="
    )

    target_date = target_date or prev_trading_day()
    logger.info(f"Target date: {target_date}")

    # M1: Data ingestion
    with _log_step(db, target_date, "m1_data_ingestion", strategy_hash):
        run_m1(db, target_date)

    # Compute technical indicators
    with _log_step(db, target_date, "indicators", strategy_hash):
        indicator_count = run_indicators(db, target_date, strategy)
    if indicator_count == 0:
        logger.error("No indicators computed — cannot continue pipeline")
        return

    # M2: Market regime detection
    with _log_step(db, target_date, "m2_regime", strategy_hash):
        regime_result = classify_regime(db, target_date, strategy=strategy)
    regime = regime_result.regime.value
    logger.info(
        f"[M2] Regime: {regime} (score={regime_result.score:.1f}, "
        f"crash={regime_result.crash_warning}, {regime_result.exposure})"
    )

    # Persist regime to market_regime_log for stability rule
    try:
        db.execute(
            text("""
                INSERT INTO market_regime_log (date, regime, score, crash_warning, strategy_hash)
                VALUES (:d, :r, :s, :c, :h)
                ON CONFLICT (date) DO UPDATE SET
                    regime = EXCLUDED.regime, score = EXCLUDED.score,
                    crash_warning = EXCLUDED.crash_warning, strategy_hash = EXCLUDED.strategy_hash
            """),
            {"d": target_date, "r": regime, "s": regime_result.score,
             "c": regime_result.crash_warning, "h": strategy_hash},
        )
    except Exception:
        db.rollback()

    # v16: Bull entry protocol (gates capital deployment during Bear recovery)
    if regime in ("Bear", "Full Bear") and strategy.regime.bull_entry_protocol.enabled:
        from momentum_edge.engine.bull_entry import evaluate_bull_entry_phase
        bull_result = evaluate_bull_entry_phase(
            db, target_date, regime,
            config=strategy.regime.bull_entry_protocol,
        )
        logger.info(f"[BullEntry] Phase: {bull_result.phase.value} — {bull_result.reason}")

    # M3: Sector rotation ranking
    with _log_step(db, target_date, "m3_sector_rotation", strategy_hash):
        sector_config = strategy.scoring.get_module("sector")
        sector_params = sector_config.params if sector_config else {}
        sector_ranks = rank_sectors(db, target_date, params=sector_params)
    total_sectors = len(sector_ranks)
    logger.info(f"[M3] Sectors ranked: {total_sectors}")

    # v16: Compute beta + detect PSU stocks (periodic, runs daily)
    with _log_step(db, target_date, "beta_psu_update", strategy_hash):
        _update_beta_and_psu(db, target_date)

    # Universe filter: apply hard blocks from strategy
    with _log_step(db, target_date, "universe_filter", strategy_hash):
        stocks = db.query(Stock).filter(Stock.is_active.is_(True)).all()
        eligible = []
        filtered_out = 0
        for stock in stocks:
            result = passes_hard_filters(db, stock, target_date, strategy=strategy)
            if result.passes:
                eligible.append(stock)
            else:
                filtered_out += 1

    logger.info(
        f"[Universe] {len(eligible)} eligible, {filtered_out} filtered out "
        f"(from {len(stocks)} active)"
    )

    # Load scaled_score from indicators for eligible stocks
    indicator_scores = {}
    rows = db.execute(text(
        "SELECT stock_id, scaled_score FROM indicators WHERE date = :d"
    ), {"d": target_date}).fetchall()
    for row in rows:
        indicator_scores[row[0]] = row[1] or 0.0

    scored_count = 0
    passed_trend = 0

    # Get module params from strategy
    fund_config = strategy.scoring.get_module("fundamental_bonus")
    fund_params = fund_config.params if fund_config else {}
    tech_config = strategy.scoring.get_module("technical")
    tech_params = tech_config.params if tech_config else {}
    breakout_config = strategy.scoring.get_module("breakout")
    breakout_params = breakout_config.params if breakout_config else {}
    accum_config = strategy.scoring.get_module("accumulation")
    accum_params = accum_config.params if accum_config else {}

    for stock in eligible:
        # Scaled momentum score (from indicators — already computed with vol scaling)
        scaled_score = indicator_scores.get(stock.id, 0.0)

        # Fundamental bonus
        f_bonus = calculate_fundamental_bonus(
            db, stock.id, stock.symbol, target_date, params=fund_params
        )

        # Sector bonus
        sector_bonus = get_sector_score(
            sector_ranks, stock.sector, total_sectors, params=sector_params
        )

        # M7: Trend template (8 conditions)
        trend = passes_trend_template(
            db, stock.id, stock.symbol, target_date, params=tech_params
        )
        technical_score = trend.technical_score
        if trend.passes:
            passed_trend += 1

        # M8: Breakout patterns (only for stocks passing trend template)
        obv_bonus = 0
        breakout_score = 0.0
        if trend.passes:
            pattern = detect_pattern(
                db, stock.id, stock.symbol, target_date, params=breakout_params
            )
            breakout_score = pattern.breakout_score
            obv_bonus = pattern.obv_bonus

        # M6: Accumulation (OBV bonus + A/D + institutional flow)
        accum = score_accumulation(
            db, stock.id, stock.symbol, target_date,
            obv_bonus=obv_bonus, params=accum_params,
        )
        accumulation_sc = accum["total"]

        # M9: Composite score
        compute_composite(
            db, stock.id, target_date,
            scaled_score=scaled_score,
            fundamental_bonus=float(f_bonus),
            sector_bonus=sector_bonus,
            technical_score=technical_score,
            accumulation_score=accumulation_sc,
            breakout_score=breakout_score,
            scoring_config=strategy.scoring,
            strategy_hash=strategy_hash,
        )
        scored_count += 1

    db.commit()
    logger.info(
        f"[M4-M9] Scored {scored_count} eligible stocks, "
        f"{passed_trend} passed trend template"
    )

    # M10: Generate watchlist
    with _log_step(db, target_date, "m10_watchlist", strategy_hash):
        watchlist_count = generate_watchlist(
            db, target_date, regime, sector_ranks,
            strategy=strategy,
        )

    # ── v16: Fast crash detection ─────────────────────────────────────
    with _log_step(db, target_date, "fast_crash", strategy_hash):
        from momentum_edge.engine.fast_crash import detect_fast_crash

        crash_result = detect_fast_crash(db, target_date, config=strategy.regime.fast_crash)
        if crash_result.is_active:
            logger.warning(f"[FastCrash] {crash_result.reason}")

    # ── v16: Position lifecycle ───────────────────────────────────────
    with _log_step(db, target_date, "positions", strategy_hash):
        _update_open_positions(db, target_date, regime, regime_result.crash_warning, strategy)

    # ── v16: Turnaround watch ─────────────────────────────────────────
    with _log_step(db, target_date, "turnaround_scan", strategy_hash):
        from momentum_edge.engine.turnaround import scan_turnarounds

        turnarounds = scan_turnarounds(db, target_date, strategy=strategy)
        if turnarounds:
            active = sum(1 for t in turnarounds if not t.suppressed)
            logger.info(f"[Turnaround] {active} active, {len(turnarounds) - active} suppressed")

    logger.info(f"=== Pipeline finished for {target_date} [{strategy_hash}] ===")
    logger.info(
        f"  Regime: {regime} ({regime_result.exposure}) | "
        f"Trend pass: {passed_trend} | Watchlist: {watchlist_count} stocks"
    )
