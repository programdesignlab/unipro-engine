"""MomentumEdge CLI entry point."""

import sys
from datetime import date

import rich_click as click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def _get_db():
    from momentum_edge.db.session import SessionLocal
    return SessionLocal()


@click.group()
def cli():
    """MomentumEdge — Automated NSE Stock Scanner & Ranking System"""
    pass


@cli.command()
def status():
    """Show DB connection status and table row counts."""
    from momentum_edge.db.session import engine
    from sqlalchemy import text

    tables = [
        "stocks", "sector_data", "eod_prices", "delivery_data",
        "fundamentals", "indicators", "scores", "watchlist",
    ]

    console.print(Panel("[bold cyan]MomentumEdge[/bold cyan] — System Status", expand=False))

    try:
        with engine.connect() as conn:
            console.print(f"[green]✓[/green] DB connected: {engine.url}")
            t = Table("Table", "Rows", show_header=True, header_style="bold")
            for tbl in tables:
                row = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).fetchone()
                count = row[0] if row else 0
                t.add_row(tbl, str(count))
            console.print(t)
    except Exception as e:
        console.print(f"[red]✗ DB error:[/red] {e}")
        sys.exit(1)

    # Parquet status
    from momentum_edge.data.parquet_store import PRICE_FILE, DELIVERY_FILE, NIFTY_FILE, _read
    console.print()
    pt = Table("Parquet file", "Rows", show_header=True, header_style="bold")
    for label, path in [
        ("price_data.parquet", PRICE_FILE),
        ("delivery_data.parquet", DELIVERY_FILE),
        ("nifty50_index.parquet", NIFTY_FILE),
    ]:
        df = _read(path)
        pt.add_row(label, str(len(df)) if not df.empty else "—")
    console.print(pt)


@cli.command()
@click.option("--symbols", "-s", multiple=True, help="Specific symbols to sync")
@click.option("--index", type=click.Choice(["nifty50", "nifty500"]), default="nifty50", show_default=True,
              help="Index universe to sync")
def sync_universe(symbols, index):
    """Sync stock master list from yfinance metadata."""
    from momentum_edge.data.stock_universe import sync_stock_universe

    db = _get_db()
    sym_list = list(symbols) if symbols else None
    label = f"{len(sym_list)} symbols" if sym_list else index.upper()
    console.print(f"[cyan]Syncing {label}...[/cyan]")

    try:
        count = sync_stock_universe(db, sym_list, index=index)
        console.print(f"[green]✓[/green] Synced {count} stocks")
    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        sys.exit(1)
    finally:
        db.close()


@cli.command()
@click.option("--period", default="10y", show_default=True, help="yfinance period string (e.g. 10y, 2y, 6mo)")
@click.option("--symbols", "-s", multiple=True, help="Limit to specific symbols")
def bootstrap(period, symbols):
    """Bootstrap full historical OHLCV from yfinance (run once)."""
    from momentum_edge.data.prices import bootstrap_prices

    db = _get_db()
    sym_list = list(symbols) if symbols else None
    console.print(f"[cyan]Bootstrapping {period} history...[/cyan]")

    try:
        bootstrap_prices(db, symbols=sym_list, period=period)
        console.print(f"[green]✓[/green] Bootstrap complete")
    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        sys.exit(1)
    finally:
        db.close()


@cli.command()
@click.option("--years", default=10, show_default=True, help="Years of history to fetch")
@click.option("--symbols", "-s", multiple=True, help="Limit to specific symbols")
def bootstrap_delivery(years, symbols):
    """Bootstrap full historical delivery data from NSE via jugaad-data (run once)."""
    from momentum_edge.data.delivery import bootstrap_delivery as _bootstrap

    db = _get_db()
    sym_list = list(symbols) if symbols else None
    console.print(f"[cyan]Bootstrapping {years}y delivery data...[/cyan]")
    try:
        _bootstrap(db, symbols=sym_list, years=years)
        console.print(f"[green]✓[/green] Delivery bootstrap complete")
    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        sys.exit(1)
    finally:
        db.close()


@cli.command()
@click.option("--years", default=2, show_default=True, help="Years of history (NSE archives ~2yr)")
def bootstrap_delivery_bulk(years):
    """Bootstrap delivery data from NSE bulk CSV files (fast, recommended)."""
    from momentum_edge.data.delivery import bootstrap_delivery_bulk as _bootstrap_bulk

    db = _get_db()
    console.print(f"[cyan]Bootstrapping {years}y delivery data via NSE bulk CSV...[/cyan]")
    try:
        _bootstrap_bulk(db, years=years)
        console.print(f"[green]✓[/green] Bulk delivery bootstrap complete")
    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        sys.exit(1)
    finally:
        db.close()


@cli.command()
@click.option("--symbols", "-s", multiple=True, help="Limit to specific symbols")
def sync_fundamentals(symbols):
    """Sync quarterly fundamentals from yfinance for all stocks."""
    from momentum_edge.data.fundamentals import sync_fundamentals as _sync

    db = _get_db()
    sym_list = list(symbols) if symbols else None
    console.print(f"[cyan]Syncing fundamentals...[/cyan]")
    try:
        _sync(db, symbols=sym_list)
        console.print(f"[green]✓[/green] Fundamentals sync complete")
    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        sys.exit(1)
    finally:
        db.close()


@cli.command()
@click.option("--date", "target_date", default=None, help="Target date YYYY-MM-DD (default: last trading day)")
def ingest(target_date):
    """Run M1 data ingestion for a single trading day (prices + delivery)."""
    from momentum_edge.data.prices import ingest_daily_prices
    from momentum_edge.data.delivery import ingest_daily_delivery
    from momentum_edge.data.nse_indices import fetch_nifty50_close
    from momentum_edge.utils.date_utils import prev_trading_day

    d = date.fromisoformat(target_date) if target_date else prev_trading_day()
    db = _get_db()

    console.print(f"[cyan]Ingesting data for {d}...[/cyan]")
    try:
        prices = ingest_daily_prices(db, d)
        delivery = ingest_daily_delivery(db, d)
        nifty = fetch_nifty50_close(d)
        console.print(f"[green]✓[/green] Prices: {prices} stocks")
        console.print(f"[green]✓[/green] Delivery: {delivery} stocks")
        if nifty:
            console.print(f"[green]✓[/green] Nifty 50 close: {nifty:.2f}")
    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        sys.exit(1)
    finally:
        db.close()


@cli.command()
@click.option("--date", "target_date", default=None, help="Target date YYYY-MM-DD (default: last trading day)")
def run(target_date):
    """Run the full pipeline (M1 → M10) for a trading day."""
    from momentum_edge.pipeline.runner import run_pipeline
    from momentum_edge.utils.date_utils import prev_trading_day

    d = date.fromisoformat(target_date) if target_date else prev_trading_day()
    db = _get_db()

    console.print(Panel(f"[bold]Running pipeline for {d}[/bold]", expand=False))
    try:
        run_pipeline(db, d)
        console.print(f"[green]✓[/green] Pipeline complete")
    except Exception as e:
        console.print(f"[red]✗ Pipeline failed:[/red] {e}")
        sys.exit(1)
    finally:
        db.close()


@cli.command()
@click.option("--date", "target_date", default=None, help="Target date YYYY-MM-DD (default: last trading day)")
@click.option("--top", default=20, show_default=True, help="Number of stocks to show")
def watchlist(target_date, top):
    """Show the ranked watchlist for a given date."""
    from sqlalchemy import text as sql_text
    from momentum_edge.utils.date_utils import prev_trading_day

    d = date.fromisoformat(target_date) if target_date else prev_trading_day()
    db = _get_db()

    try:
        rows = db.execute(
            sql_text("""
                SELECT w.rank, s.symbol, w.composite_score, w.pattern_type,
                       w.regime, w.stop_loss_level, w.sector_name, w.sector_rank
                FROM watchlist w
                JOIN stocks s ON s.id = w.stock_id
                WHERE w.date = :target_date
                ORDER BY w.rank
                LIMIT :top
            """),
            {"target_date": d, "top": top},
        ).fetchall()

        if not rows:
            console.print(f"[yellow]No watchlist found for {d}[/yellow]")
            return

        regime = rows[0][4] if rows else "Unknown"
        console.print(Panel(
            f"[bold cyan]Watchlist — {d}[/bold cyan] | Regime: [bold]{regime}[/bold]",
            expand=False,
        ))

        t = Table(
            "#", "Symbol", "Score", "Pattern", "Stop Loss",
            "Sector", "Sec Rank",
            show_header=True, header_style="bold",
        )
        for row in rows:
            rank, symbol, score, pattern, regime, stop, sector, sec_rank = row
            t.add_row(
                str(rank),
                f"[bold]{symbol}[/bold]",
                f"{score:.1f}" if score else "—",
                pattern or "—",
                f"{stop:.2f}" if stop else "—",
                sector or "—",
                str(sec_rank) if sec_rank else "—",
            )
        console.print(t)

        # Show score breakdown for top 5
        top_rows = db.execute(
            sql_text("""
                SELECT s.symbol, sc.momentum_score, sc.fundamental_score,
                       sc.sector_score, sc.technical_score, sc.accumulation_score,
                       sc.breakout_score, sc.composite_score
                FROM scores sc
                JOIN stocks s ON s.id = sc.stock_id
                WHERE sc.date = :target_date
                ORDER BY sc.composite_score DESC
                LIMIT 5
            """),
            {"target_date": d},
        ).fetchall()

        if top_rows:
            console.print()
            console.print("[bold]Top 5 — Score Breakdown[/bold]")
            bt = Table(
                "Symbol", "Mom/40", "Fund/25", "Sect/20", "Tech/15", "Accum/15", "Brk/10", "Total/125",
                show_header=True, header_style="bold",
            )
            for r in top_rows:
                bt.add_row(
                    f"[bold]{r[0]}[/bold]",
                    f"{r[1]:.1f}" if r[1] else "—",
                    f"{r[2]:.1f}" if r[2] else "—",
                    f"{r[3]:.1f}" if r[3] else "—",
                    f"{r[4]:.1f}" if r[4] else "—",
                    f"{r[5]:.1f}" if r[5] else "—",
                    f"{r[6]:.1f}" if r[6] else "—",
                    f"{r[7]:.1f}" if r[7] else "—",
                )
            console.print(bt)

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        sys.exit(1)
    finally:
        db.close()


@cli.command()
@click.option("--date", "target_date", default=None, help="Target date YYYY-MM-DD (default: last trading day)")
def scan(target_date):
    """Run scan only (indicators + M2-M9 scoring) without data ingestion."""
    from momentum_edge.pipeline.runner import run_indicators
    from momentum_edge.scanner.market_regime import classify_regime
    from momentum_edge.scanner.sector_rotation import rank_sectors, get_sector_score
    from momentum_edge.scanner.trend_template import passes_trend_template
    from momentum_edge.scanner.breakout_patterns import detect_pattern
    from momentum_edge.ranking.momentum_score import score_momentum
    from momentum_edge.ranking.canslim_score import apply_canslim_filter
    from momentum_edge.ranking.accumulation_score import score_accumulation
    from momentum_edge.ranking.composite_score import compute_composite
    from momentum_edge.ranking.watchlist import generate_watchlist
    from momentum_edge.db.models import Stock
    from momentum_edge.utils.date_utils import prev_trading_day

    d = date.fromisoformat(target_date) if target_date else prev_trading_day()
    db = _get_db()

    console.print(Panel(f"[bold]Scanning for {d}[/bold]", expand=False))
    try:
        # Indicators
        count = run_indicators(db, d)
        console.print(f"[green]✓[/green] Indicators: {count} stocks")

        # M2
        regime_result = classify_regime(db, d)
        console.print(
            f"[green]✓[/green] Regime: [bold]{regime_result.regime.value}[/bold] "
            f"({regime_result.exposure})"
        )

        # M3
        sector_ranks = rank_sectors(db, d)
        console.print(f"[green]✓[/green] Sectors ranked: {len(sector_ranks)}")

        # M4-M9 for all stocks
        stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
        scored = 0
        trend_pass = 0

        for stock in stocks:
            mom = score_momentum(stock.symbol, d)
            canslim = apply_canslim_filter(db, stock.id, stock.symbol)
            sec_score = get_sector_score(sector_ranks, stock.sector)
            trend = passes_trend_template(db, stock.id, stock.symbol, d)
            accum = score_accumulation(db, stock.id, stock.symbol, d)

            if trend.passes:
                trend_pass += 1
                pattern = detect_pattern(db, stock.id, stock.symbol, d)
                brk_score = pattern.breakout_score
            else:
                brk_score = 0.0

            compute_composite(
                db, stock.id, d,
                momentum_score=mom["total"],
                fundamental_score=canslim.score if canslim.passes else 0.0,
                sector_score=sec_score,
                technical_score=trend.technical_score,
                accumulation_score=accum["total"],
                breakout_score=brk_score,
            )
            scored += 1

        db.commit()
        console.print(f"[green]✓[/green] Scored: {scored} stocks, {trend_pass} passed trend template")

        # M10
        wl_count = generate_watchlist(db, d, regime_result.regime.value, sector_ranks)
        console.print(f"[green]✓[/green] Watchlist: {wl_count} stocks")
        console.print(f"\n[cyan]Run[/cyan] [bold]watchlist --date {d}[/bold] [cyan]to view results[/cyan]")

    except Exception as e:
        console.print(f"[red]✗ Scan failed:[/red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


def main():
    cli()


if __name__ == "__main__":
    main()
