"""M11 — Master pipeline orchestrator."""

from datetime import date

from loguru import logger
from sqlalchemy.orm import Session

from momentum_edge.utils.date_utils import prev_trading_day


def run_m1(db: Session, target_date: date) -> None:
    """Run Module 1: data ingestion."""
    from momentum_edge.data.prices import ingest_daily_prices
    from momentum_edge.data.nse_indices import fetch_nifty50_close
    from momentum_edge.data.delivery import ingest_daily_delivery

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


def run_indicators(db: Session, target_date: date) -> int:
    """Compute and store technical indicators for all stocks."""
    from momentum_edge.scanner.indicators import compute_and_store_indicators

    logger.info(f"[Indicators] Computing for {target_date}")
    count = compute_and_store_indicators(db, target_date)
    logger.info(f"[Indicators] {count} stocks computed")
    return count


def run_pipeline(db: Session, target_date: date | None = None) -> None:
    """Run the full M1→M10 pipeline for target_date (defaults to last trading day)."""
    from momentum_edge.db.models import Stock
    from momentum_edge.scanner.market_regime import classify_regime
    from momentum_edge.scanner.sector_rotation import rank_sectors, get_sector_score
    from momentum_edge.scanner.trend_template import passes_trend_template
    from momentum_edge.scanner.breakout_patterns import detect_pattern
    from momentum_edge.ranking.momentum_score import score_momentum
    from momentum_edge.ranking.canslim_score import apply_canslim_filter
    from momentum_edge.ranking.accumulation_score import score_accumulation
    from momentum_edge.ranking.composite_score import compute_composite
    from momentum_edge.ranking.watchlist import generate_watchlist

    target_date = target_date or prev_trading_day()
    logger.info(f"=== MomentumEdge Pipeline — {target_date} ===")

    # M1: Data ingestion
    run_m1(db, target_date)

    # Compute technical indicators (feeds M2, M4, M7)
    indicator_count = run_indicators(db, target_date)
    if indicator_count == 0:
        logger.error("No indicators computed — cannot continue pipeline")
        return

    # M2: Market regime detection
    regime_result = classify_regime(db, target_date)
    regime = regime_result.regime.value

    # M3: Sector rotation ranking
    sector_ranks = rank_sectors(db, target_date)

    # Get all active stocks
    stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
    logger.info(f"[Pipeline] Processing {len(stocks)} active stocks through M4-M9")

    scored_count = 0
    passed_trend = 0

    for stock in stocks:
        # M4: Momentum score
        mom = score_momentum(stock.symbol, target_date)
        momentum_score = mom["total"]

        # M5: CANSLIM filter
        canslim = apply_canslim_filter(db, stock.id, stock.symbol)
        fundamental_score = canslim.score if canslim.passes else 0.0

        # M3: Sector score for this stock
        sector_score = get_sector_score(sector_ranks, stock.sector)

        # M7: Trend template
        trend = passes_trend_template(db, stock.id, stock.symbol, target_date)
        technical_score = trend.technical_score
        if trend.passes:
            passed_trend += 1

        # M6: Accumulation
        accum = score_accumulation(db, stock.id, stock.symbol, target_date)
        accumulation_sc = accum["total"]

        # M8: Breakout patterns (only for stocks passing trend template)
        if trend.passes:
            pattern = detect_pattern(db, stock.id, stock.symbol, target_date)
            breakout_score = pattern.breakout_score
        else:
            breakout_score = 0.0

        # M9: Composite score
        compute_composite(
            db, stock.id, target_date,
            momentum_score=momentum_score,
            fundamental_score=fundamental_score,
            sector_score=sector_score,
            technical_score=technical_score,
            accumulation_score=accumulation_sc,
            breakout_score=breakout_score,
        )
        scored_count += 1

    db.commit()
    logger.info(f"[M4-M9] Scored {scored_count} stocks, {passed_trend} passed trend template")

    # M10: Generate watchlist
    watchlist_count = generate_watchlist(db, target_date, regime, sector_ranks)

    logger.info(f"=== Pipeline finished for {target_date} ===")
    logger.info(
        f"  Regime: {regime} ({regime_result.exposure}) | "
        f"Trend pass: {passed_trend} | Watchlist: {watchlist_count} stocks"
    )
