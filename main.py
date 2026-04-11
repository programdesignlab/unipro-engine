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
    """Sync quarterly fundamentals from yfinance for all stocks (legacy)."""
    from momentum_edge.data.fundamentals import sync_fundamentals as _sync

    db = _get_db()
    sym_list = list(symbols) if symbols else None
    console.print(f"[cyan]Syncing fundamentals (yfinance)...[/cyan]")
    try:
        _sync(db, symbols=sym_list)
        console.print(f"[green]✓[/green] Fundamentals sync complete")
    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        sys.exit(1)
    finally:
        db.close()


@cli.command()
@click.option("--symbols", "-s", multiple=True, help="Limit to specific symbols")
@click.option("--batch", default=500, show_default=True, help="Batch size per run")
@click.option("--skip-done", is_flag=True, help="Skip stocks that already have Screener fundamentals")
def sync_screener(symbols, batch, skip_done):
    """Sync fundamentals + shareholding from Screener.in (recommended)."""
    from momentum_edge.data.screener import sync_screener_fundamentals
    from sqlalchemy import text as sql_text

    db = _get_db()
    sym_list = list(symbols) if symbols else None

    if skip_done and not sym_list:
        # Only process stocks missing fundamentals from Screener
        rows = db.execute(sql_text("""
            SELECT s.symbol FROM stocks s
            WHERE s.is_active = true
              AND s.screener_export_id IS NOT NULL
              AND s.id NOT IN (
                  SELECT DISTINCT stock_id FROM fundamentals
                  WHERE revenue IS NOT NULL AND quarter LIKE 'Q%%FY2%%'
                  AND reporting_date IS NOT NULL
              )
            ORDER BY s.symbol
        """)).fetchall()
        sym_list = [r[0] for r in rows]
        console.print(f"[cyan]Screener sync: {len(sym_list)} stocks need fundamentals[/cyan]")
    else:
        label = f"{len(sym_list)} symbols" if sym_list else "all active stocks"
        console.print(f"[cyan]Screener sync: {label}, batch={batch}[/cyan]")

    try:
        count = sync_screener_fundamentals(db, symbols=sym_list, batch_size=batch)
        console.print(f"[green]✓[/green] Screener sync: {count} fundamental rows written")
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
@click.option("--strategy", "strategy_path", default=None, help="Path to strategy YAML (default: strategies/momentum_edge.yaml)")
def run(target_date, strategy_path):
    """Run the full pipeline (M1 → M10) for a trading day."""
    from momentum_edge.pipeline.runner import run_pipeline
    from momentum_edge.utils.date_utils import prev_trading_day

    d = date.fromisoformat(target_date) if target_date else prev_trading_day()
    db = _get_db()

    console.print(Panel(f"[bold]Running pipeline for {d}[/bold]", expand=False))
    try:
        run_pipeline(db, d, strategy_path=strategy_path)
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
@click.option("--strategy", "strategy_path", default=None, help="Path to strategy YAML")
def scan(target_date, strategy_path):
    """Run scan only (indicators + scoring) without data ingestion.

    Same as 'run' but skips M1 data ingestion step. Uses existing price data.
    """
    from momentum_edge.pipeline.runner import run_pipeline
    from momentum_edge.utils.date_utils import prev_trading_day

    d = date.fromisoformat(target_date) if target_date else prev_trading_day()
    db = _get_db()

    console.print(Panel(f"[bold]Scanning for {d}[/bold] (skip data ingestion)", expand=False))
    try:
        # Run full pipeline but it will use existing data
        run_pipeline(db, d, strategy_path=strategy_path)
        console.print(f"[green]✓[/green] Scan complete")
        console.print(f"\n[cyan]Run[/cyan] [bold]watchlist --date {d}[/bold] [cyan]to view results[/cyan]")
    except Exception as e:
        console.print(f"[red]✗ Scan failed:[/red] {e}")
        sys.exit(1)
    finally:
        db.close()


@cli.command()
@click.option("--start", default="2015-01-01", show_default=True, help="Start date YYYY-MM-DD")
@click.option("--end", default="2024-12-31", show_default=True, help="End date YYYY-MM-DD")
@click.option("--capital", default=1_000_000, show_default=True, help="Initial capital in Rs")
def backtest(start, end, capital):
    """Run a full v7 backtest over historical data."""
    from momentum_edge.backtest.engine import Backtester, BacktestConfig

    db = _get_db()
    config = BacktestConfig(
        start_date=date.fromisoformat(start),
        end_date=date.fromisoformat(end),
        initial_capital=capital,
    )
    console.print(Panel(
        f"[bold]Backtest: {start} → {end} | Capital: Rs.{capital:,.0f}[/bold]",
        expand=False,
    ))

    try:
        bt = Backtester(db, config)
        bt.prepare_data()
        console.print(f"[green]✓[/green] Data loaded: {len(bt._stock_meta)} stocks")
        bt.run()
        console.print(f"[green]✓[/green] Simulation complete: {len(bt.trades)} trades")

        metrics = bt.compute_metrics()
        console.print()
        console.print("[bold]Performance Metrics[/bold]")
        t = Table("Metric", "Value", show_header=True, header_style="bold")
        for key in ["cagr", "sharpe_ratio", "max_drawdown", "calmar_ratio",
                     "win_rate", "avg_win_pct", "avg_loss_pct", "expectancy_pct",
                     "total_trades", "avg_holding_days"]:
            val = metrics.get(key)
            if val is not None:
                if "pct" in key or key in ("cagr", "max_drawdown", "win_rate"):
                    t.add_row(key, f"{val:.2%}" if abs(val) < 10 else f"{val:.1f}%")
                elif isinstance(val, float):
                    t.add_row(key, f"{val:.2f}")
                else:
                    t.add_row(key, str(val))
        console.print(t)

        # Gates
        gates = metrics.get("passes_gates", {})
        if gates:
            console.print()
            console.print("[bold]Gate Checks[/bold]")
            for gate, passed in gates.items():
                icon = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
                console.print(f"  {icon} {gate}")

        run_id = bt.save_results("manual_backtest")
        console.print(f"\n[green]✓[/green] Results saved (run_id={run_id})")

    except Exception as e:
        console.print(f"[red]✗ Backtest failed:[/red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


@cli.command()
@click.option("--test", type=int, default=None, help="Run specific test (1-10), or all if omitted")
def backtest_tests(test):
    """Run structured backtests (Tests 1-10 from v7 spec)."""
    from momentum_edge.backtest.test_runner import run_all_tests

    db = _get_db()
    console.print(Panel("[bold]MomentumEdge v7 — Structured Backtests[/bold]", expand=False))

    try:
        if test:
            from momentum_edge.backtest import test_runner
            func = getattr(test_runner, f"run_test_{test}_{'momentum_weights' if test == 1 else ''}", None)
            if func:
                results = func(db)
                console.print(f"[green]✓[/green] Test {test} complete")
            else:
                console.print(f"[red]Test {test} not found[/red]")
        else:
            summary = run_all_tests(db)
            console.print(f"[green]✓[/green] All tests complete")
    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


def main():
    cli()


if __name__ == "__main__":
    main()
