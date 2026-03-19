"""M11 — Master pipeline orchestrator (v7)."""

from datetime import date

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.utils.date_utils import prev_trading_day


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

    # v7: FII/DII, bulk deals, ASM/ESM
    ingest_fii_dii(db, target_date)
    deals = ingest_bulk_deals(db, target_date)
    logger.info(f"[M1] Bulk/block deals: {deals}")

    asm, esm = sync_surveillance(db)
    if asm or esm:
        logger.info(f"[M1] ASM: {asm}, ESM: {esm}")


def run_indicators(db: Session, target_date: date) -> int:
    """Compute and store technical indicators for all stocks."""
    from momentum_edge.scanner.indicators import compute_and_store_indicators

    logger.info(f"[Indicators] Computing for {target_date}")
    count = compute_and_store_indicators(db, target_date)
    logger.info(f"[Indicators] {count} stocks computed")
    return count


def run_pipeline(db: Session, target_date: date | None = None) -> None:
    """Run the full v7 pipeline for target_date (defaults to last trading day).

    Flow:
    1. M1: Data ingestion (prices, delivery, FII/DII, deals, surveillance)
    2. Indicators: MA, momentum, OBV, A/D, vol scaling, RS rank
    3. M2: Market regime (6 signals + crash indicator)
    4. M3: Sector rotation ranking
    5. Universe filter: 4 hard filters (market cap, liquidity, ASM, EPS)
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
    from momentum_edge.ranking.composite_score import compute_composite
    from momentum_edge.ranking.watchlist import generate_watchlist

    target_date = target_date or prev_trading_day()
    logger.info(f"=== MomentumEdge v7 Pipeline — {target_date} ===")

    # M1: Data ingestion
    run_m1(db, target_date)

    # Compute technical indicators (includes momentum scoring, vol scaling, RS rank)
    indicator_count = run_indicators(db, target_date)
    if indicator_count == 0:
        logger.error("No indicators computed — cannot continue pipeline")
        return

    # M2: Market regime detection (6 signals + crash indicator)
    regime_result = classify_regime(db, target_date)
    regime = regime_result.regime.value
    logger.info(
        f"[M2] Regime: {regime} (score={regime_result.score:.1f}, "
        f"crash={regime_result.crash_warning}, {regime_result.exposure})"
    )

    # M3: Sector rotation ranking
    sector_ranks = rank_sectors(db, target_date)
    total_sectors = len(sector_ranks)
    logger.info(f"[M3] Sectors ranked: {total_sectors}")

    # Get all active stocks
    stocks = db.query(Stock).filter(Stock.is_active.is_(True)).all()

    # Universe filter: apply 4 hard filters
    eligible = []
    filtered_out = 0
    for stock in stocks:
        result = passes_hard_filters(db, stock, target_date)
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

    for stock in eligible:
        # Scaled momentum score (from indicators — already computed with vol scaling)
        scaled_score = indicator_scores.get(stock.id, 0.0)

        # Fundamental bonus (-5 to +20)
        f_bonus = calculate_fundamental_bonus(db, stock.id, stock.symbol, target_date)

        # Sector bonus (+10, 0, or -5)
        sector_bonus = get_sector_score(sector_ranks, stock.sector, total_sectors)

        # M7: Trend template (8 conditions)
        trend = passes_trend_template(db, stock.id, stock.symbol, target_date)
        technical_score = trend.technical_score
        if trend.passes:
            passed_trend += 1

        # M8: Breakout patterns (only for stocks passing trend template)
        obv_bonus = 0
        breakout_score = 0.0
        if trend.passes:
            pattern = detect_pattern(db, stock.id, stock.symbol, target_date)
            breakout_score = pattern.breakout_score
            obv_bonus = pattern.obv_bonus

        # M6: Accumulation (OBV bonus + A/D + institutional flow)
        accum = score_accumulation(
            db, stock.id, stock.symbol, target_date, obv_bonus=obv_bonus
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
        )
        scored_count += 1

    db.commit()
    logger.info(
        f"[M4-M9] Scored {scored_count} eligible stocks, "
        f"{passed_trend} passed trend template"
    )

    # M10: Generate watchlist
    watchlist_count = generate_watchlist(db, target_date, regime, sector_ranks)

    logger.info(f"=== Pipeline finished for {target_date} ===")
    logger.info(
        f"  Regime: {regime} ({regime_result.exposure}) | "
        f"Trend pass: {passed_trend} | Watchlist: {watchlist_count} stocks"
    )
