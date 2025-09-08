# ── src/cli.py ────────────────────────────────────────────────────────
from __future__ import annotations

import click
from pathlib import Path
import yaml
from src.utils import norm_sym                                                       # NEW

from src.download    import main as download_main
from src.backtest    import main as backtest_main
from src.paper       import run  as paper_run
from src.performance import equity_curve, max_drawdown, sharpe_ratio


# ─────────────────────────────────────────────────────────────────────
def _load_cfg() -> dict:
    """Best-effort YAML reader – returns {} if missing / invalid."""
    cfg_path = Path("config.yaml")
    if not cfg_path.exists():
        return {}
    try:
        return yaml.safe_load(cfg_path.read_text()) or {}
    except Exception as exc:                                       # pragma: no cover
        click.echo(f"⚠️  Could not parse config.yaml ({exc}); ignoring.")
        return {}


CFG = _load_cfg()   # single read at import time
# ─────────────────────────────────────────────────────────────────────


@click.group()
def cli() -> None:
    """QuantDash: download data, backtest, paper-trade, performance."""
    pass


# ------------------------------------------------------------------- #
@cli.command("download")
@click.option("--symbol",    required=True, help="Ticker, e.g. SPY")
@click.option("--start",     required=True, help="YYYY-MM-DD")
@click.option("--end",       required=True, help="YYYY-MM-DD")
@click.option(
    "--timeframe",
    default="1Day",
    help="1Day | 1Hour | 15Min | 1Min",
)
def download(symbol: str, start: str, end: str, timeframe: str) -> None:
    """Fetch raw bars from Alpaca → Parquet."""
    download_main(
        ["--symbol", symbol, "--start", start, "--end", end, "--timeframe", timeframe]
    )


# ------------------------------------------------------------------- #
@cli.command("backtest")
@click.option("--symbol", required=True, help="Ticker, e.g. SPY")
@click.option("--short",  default=10,  type=int, help="Short SMA window")
@click.option("--long",   default=50,  type=int, help="Long  SMA window")
def backtest(symbol: str, short: int, long: int) -> None:
    """Run MA-crossover back-test."""
    backtest_main(["--symbol", symbol, "--short", str(short), "--long", str(long)])


# ------------------------------------------------------------------- #
@cli.command("paper")
@click.option(
    "--symbol",
    required=False,     # ← was True
    help="Ticker(s), comma-separated – e.g. SPY  or  SPY,AAPL",
)
@click.option("--short",     type=int, help="Short SMA window")
@click.option("--long",      type=int, help="Long  SMA window")
@click.option(
    "--timeframe",
    help="1Day | 1Hour | 15Min | 1Min",
)
@click.option(
    "--interval",
    type=int,
    help="Seconds between paper-trading cycles",
)
@click.option(
    "--dashboard",
    is_flag=True,
    help="Show live Rich dashboard instead of plain stdout",
)
def paper(
    symbol: str | None,
    short: int | None,
    long: int | None,
    timeframe: str | None,
    interval: int | None,
    dashboard: bool,
) -> None:
    """
    Start the paper-trading loop.

    Any option omitted on the CLI is looked-up in **config.yaml**.
    """
    # ---------- resolve defaults ------------------------------------
    if not symbol:
        symbol = ",".join(CFG.get("symbols", []))

    # still no symbols → raise
    if not symbol:
        raise click.ClickException(
            "Missing --symbol option and no 'symbols' entry in config.yaml"
        )

    short     = short     or int(CFG.get("short",     10))
    long      = long      or int(CFG.get("long",      50))
    timeframe = timeframe or str(CFG.get("timeframe", "1Day"))
    interval  = interval  or int(CFG.get("interval",  60))

    syms = [norm_sym(s) for s in symbol.split(",") if s.strip()]

    # ---------- launch paper loop -----------------------------------
    paper_run(syms, short, long, timeframe, interval, dashboard=dashboard)


# ─────────────────────────────────────────────────────────────────
@cli.command("dl_batch")
@click.option("--symbols", required=True,
              help="Comma-separated tickers, e.g. SPY,QQQ,AAPL")
@click.option("--start",   required=True, help="YYYY-MM-DD")
@click.option("--end",     required=True, help="YYYY-MM-DD")
@click.option("--timeframe", default="1Day",
              help="1Day|1Hour|15Min|1Min")
def dl_batch(symbols: str, start: str, end: str, timeframe: str) -> None:
    """Download bars for many tickers in one command."""
    for sym in [norm_sym(s) for s in symbols.split(",") if s.strip()]:
        click.echo(f"⬇️  Downloading {sym} …")
        download_main([
            "--symbol", sym,
            "--start",  start,
            "--end",    end,
            "--timeframe", timeframe,
        ])
# ─────────────────────────────────────────────────────────────────




# ------------------------------------------------------------------- #
@cli.command("perf")
@click.option("--symbol", required=True, help="Ticker, e.g. SPY")
@click.option("--short",  default=10, type=int, help="Short SMA window")
@click.option("--long",   default=50, type=int, help="Long  SMA window")
def perf(symbol: str, short: int, long: int) -> None:
    """Compute & print performance metrics for a back-test."""
    import pandas as pd
    from src.backtest import compute_signals, backtest

    df = pd.read_parquet(f"data/raw/{symbol}_1Day.parquet").set_index("timestamp")
    sig     = compute_signals(df, short=short, long=long)
    trades  = backtest(sig)
    eq      = equity_curve(trades)

    click.echo(f"\n=== Performance for {symbol} MA{short}/{long} ===")
    click.echo("Equity curve:")
    click.echo(eq)
    click.echo(f"Max drawdown: {max_drawdown(eq):.2%}")
    click.echo(f"Sharpe ratio: {sharpe_ratio(eq):.4f}")






# ------------------------------------------------------------------- #
if __name__ == "__main__":   # pragma: no cover
    cli()
