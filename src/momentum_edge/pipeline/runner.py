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

    # M3: Sector rotation ranking
    with _log_step(db, target_date, "m3_sector_rotation", strategy_hash):
        sector_config = strategy.scoring.get_module("sector")
        sector_params = sector_config.params if sector_config else {}
        sector_ranks = rank_sectors(db, target_date, params=sector_params)
    total_sectors = len(sector_ranks)
    logger.info(f"[M3] Sectors ranked: {total_sectors}")

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

    logger.info(f"=== Pipeline finished for {target_date} [{strategy_hash}] ===")
    logger.info(
        f"  Regime: {regime} ({regime_result.exposure}) | "
        f"Trend pass: {passed_trend} | Watchlist: {watchlist_count} stocks"
    )
