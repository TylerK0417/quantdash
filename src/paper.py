# src/paper.py


from __future__ import annotations

from pathlib import Path 
import yaml
from src.logger import logger as log 

cfg_path = Path(__file__).resolve().parent.parent / "config.yaml"
cfg      = yaml.safe_load(cfg_path.read_text())
CFG = cfg 

# ── load .env so both trading & data clients see your keys ──────────────
from dotenv import load_dotenv
load_dotenv()

import argparse
import os
import random
import time
import sys 
from datetime import datetime, timedelta
from typing import List, Literal
from src.utils import norm_sym
import logging


from collections import deque           #  ← NEW
from src.dashboard import Dashboard 

from src.journal import log_equity
from src.telemetry import init_dash, LiveDashboard          # your helper file

from typing import Dict
import datetime as dt, yaml
from pathlib import Path
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests   import CryptoBarsRequest, StockBarsRequest  
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from .logger import logger          # NEW – must be before _latest_bar_live()

from src.download import load_data
from src.scheduler import schedule_task
from src.signals import compute_signals
from src.trader import Trader
from typing import List, Literal 


# ------------------------------------------------------------------
# quick CLI flag: --reset-portfolio
if "--reset-portfolio" in sys.argv:
    try:
        os.remove("data/positions.csv")
        print("🗑️  Deleted data/positions.csv – portfolio reset.")
    except FileNotFoundError:
        print("🗑️  Portfolio already empty.")
    # purge flag so argparse doesn't choke
    sys.argv.remove("--reset-portfolio")
# ------------------------------------------------------------------
try:
    from src.telemetry import init_dash, LiveDashboard
   # ← you’ll add this file next
except ModuleNotFoundError:
    LiveDashboard = None

# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────
def _tf_enum(tf: str) -> TimeFrame:
    return {
        "1Min": TimeFrame.Minute,
        "15Min": getattr(TimeFrame, "Minute15", TimeFrame.Minute),
        "1Hour": getattr(TimeFrame, "Hour", TimeFrame.Minute),
        "1Day": TimeFrame.Day,
    }[tf]



def _latest_bar_live(symbol: str, tf: str, client) -> pd.Series | None:
    """
    Return the most-recent completed bar for *symbol* at timeframe *tf*.
    • Crypto pairs (contain “/”) → CryptoHistoricalDataClient
    • Equities              → StockHistoricalDataClient
    """
    # ── CRYPTO path ──────────────────────────────────────────────────────
    if "/" in symbol:
        try:
            req = CryptoBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=_tf_enum(tf),
                limit=1,
            )
            bar_row = client.get_crypto_bars(req).df.iloc[0]   # pandas Series
            ts = bar_row.get("timestamp", bar_row.get("t"))    # column differs
            return pd.Series(
                {
                    "timestamp": pd.Timestamp(ts).tz_localize(None),
                    "open":  bar_row["open"],
                    "high":  bar_row["high"],
                    "low":   bar_row["low"],
                    "close": bar_row["close"],
                    "volume": bar_row["volume"],
                }
            )
        except Exception as exc:
            logger.warning(f"{symbol}: crypto fetch failed ({exc})")
            return None

    # ── EQUITIES path ───────────────────────────────────────────────────
    # 1. Try the “latest bar” helper (new Alpaca-py versions)
    try:
        bar_wrap = client.get_stock_latest_bar(symbol, feed=DataFeed.IEX)
    except (AttributeError, TypeError):
        try:
            bar_wrap = client.get_stock_latest_bar(symbol)  # old signature
        except Exception:
            bar_wrap = None

    bar_obj = None
    if bar_wrap:
        bar_obj = bar_wrap[symbol] if isinstance(bar_wrap, dict) else bar_wrap

    # 2. Fallback: one-bar request if helper failed
    if bar_obj is None:
        try:
            bars_df = client.get_stock_bars(
                symbol, _tf_enum(tf), feed=DataFeed.IEX, limit=1
            )
            if isinstance(bars_df, dict):      # older SDKs return dict
                bars_df = bars_df.get(symbol, pd.DataFrame())
            if not bars_df.empty:
                bar_obj = bars_df.iloc[0]
        except Exception:
            bar_obj = None

    if bar_obj is None:
        return None

    # Convert Alpaca Bar object or row into a Series
    return pd.Series(
        {
            "timestamp": pd.Timestamp(bar_obj.t).tz_localize(None),
            "open":  bar_obj.o,
            "high":  bar_obj.h,
            "low":   bar_obj.l,
            "close": bar_obj.c,
            "volume": bar_obj.v,
        }
    )


def _latest_bar_sim(last_close: float) -> pd.Series:
    pct = random.uniform(-0.001, 0.001)
    new_close = round(last_close * (1 + pct), 2)
    return pd.Series(
        {
            "timestamp": datetime.utcnow().replace(second=0, microsecond=0),
            "open": last_close,
            "high": max(last_close, new_close),
            "low": min(last_close, new_close),
            "close": new_close,
            "volume": 0,
        }
    )
# ── seed live positions even in pure-paper mode ─────────────────
def _seed_broker_positions(portfolio) -> None:
    """Fetch current Alpaca positions and inject them into the local portfolio."""
    import os
    from alpaca.trading.client import TradingClient
    from src.utils import norm_sym

    try:
        tc = TradingClient(
            os.getenv("ALPACA_API_KEY"),
            os.getenv("ALPACA_API_SECRET"),
            paper=True,               # still paper account
        )
        for pos in tc.get_all_positions():
            sym  = norm_sym(pos.symbol)
            qty  = float(pos.qty)
            entry= float(pos.avg_entry_price)
            portfolio.open_position(sym, qty, entry, stop=None, tp=None)
            print(f"🔄  Seeded {sym} {qty} @ {entry}")
    except Exception as exc:
        print(f"⚠️  Could not seed live positions: {exc}")


# ────────────────────────────────────────────────────────────────────
# Paper-trading loop
# ────────────────────────────────────────────────────────────────────
def run(
    symbols: List[str],
    short: int,
    long: int,
    timeframe: Literal["1Min", "15Min", "1Hour", "1Day"],
    interval: int,
    *,
    live: bool = False,
    dashboard: bool = False,
) -> None:
    """
    Main driver for real-time paper-trading.

    • Pulls the most-recent bar for each symbol (live API or simulated)
    • Maintains trailing stops & exits via Trader helper methods
    • Generates MA-crossover signals and places orders
    • Produces telemetry either as Rich live dashboard or plain stdout
    • Persists an equity snapshot (via log_equity) every cycle
    """
    # ── bootstrap ──────────────────────────────────────────────────
    trader   = Trader(paper= True,
                      risk_pct  = cfg.get("risk_pct", 0.01),
                      trail_pct = cfg.get("trail_pct", 0.01),
                      )
    
    log.info(
    "Config: risk_pct=%.2f %%  •  trail_pct=%.2f %%",
    trader.risk_pct * 100,
    trader.trail_pct * 100,
    )

    _seed_broker_positions(trader.portfolio)
    trader.reconcile_open_orders() 
    history  = deque(maxlen=500)          # rolling equity curve for sparkline

    # honour “--dashboard” passed verbatim (back-compat with older CLI)
    dashboard = dashboard or ("--dashboard" in sys.argv)
    if "--dashboard" in sys.argv:
        sys.argv.remove("--dashboard")    # remove so Click/argparse don’t choke

    RUNS = Path("runs"); RUNS.mkdir(exist_ok=True)
    snapshot = {
        "symbols": symbols,
        "timeframe": timeframe,
        "interval": interval,
        "short": short,
        "long": long,
        "risk_pct": cfg["risk_pct"],
        "atr_mult": cfg["atr_mult"],
        "engine": cfg.get("engine", "ma"),
    }
    snap_path = RUNS / f"run_{dt.datetime.utcnow():%Y%m%d_%H%M%S}.yaml"
    snap_path.write_text(yaml.safe_dump(snapshot))

    symbols_cfg = [norm_sym(s) for s in cfg.get("symbols", [])]

    # lazy-init Rich dashboard (safe if Rich not installed)
    dash: "LiveDashboard | None"
    if dashboard:
        try:
            from src.telemetry import init_dash        # starts Live context
            dash = init_dash()                         # returns LiveDashboard
        except Exception as e:
            print(f"⚠️  Cannot start Rich dashboard ({e}); falling back to log.")
            dashboard = False
            dash = None
    else:
        dash = None

    # market-data client (falls back to simulated bars if keyless)
    try:
        if any("/" in s for s in symbols):          # ← at least one crypto pair
            md_client = CryptoHistoricalDataClient( # live CRYPTO feed
                os.getenv("ALPACA_API_KEY"),
                os.getenv("ALPACA_API_SECRET"),
            )
        else:
            md_client = StockHistoricalDataClient(  # live EQUITY feed
                api_key=os.getenv("ALPACA_API_KEY"),
                secret_key=os.getenv("ALPACA_API_SECRET"),
            )
    except ValueError:
        print("ℹ️  Market-data auth failed; using simulated bars.")
        md_client = None

    print(
        f"▶️  Starting paper trading on {symbols} "
        f"(MA{short}/{long}, {timeframe}), every {interval}s. Ctrl+C to stop."
    )


    # ───────────────────────────────────────────────────────────────
    # ONE-CYCLE FUNCTION  —  executes every <interval> seconds
    # ───────────────────────────────────────────────────────────────
    def one_cycle() -> None:
        last_px: dict[str, float] = {}     # cache close for each symbol

        for sym in symbols:
            # 1.  Pull trailing 100 bars ----------------------------
            df = load_data(norm_sym(sym), timeframe=timeframe).tail(100)

            bar = (
                _latest_bar_live(sym, timeframe, md_client)
                if md_client is not None
                else _latest_bar_sim(df["close"].iloc[-1])
            )
            if bar is not None:
                df = pd.concat([df, bar.to_frame().T]).tail(100)

            close_px = float(df["close"].iloc[-1])
            last_px[sym] = close_px

            # 2.  Trailing stops & exits ---------------------------
            trader.update_trailing({sym: close_px}, {sym: df})
            trader.check_stops({sym: close_px})

            # 3.  Signal generation & order execution -------------
            sigs = compute_signals(df, 
                                   short=short, 
                                   long=long,
                                   thresh_pct=cfg.get("thresh_pct", 0.0),
                                   )
            trader.execute_signals(sym, sigs, df)        # pass full OHLC
            last_sig = int(sigs["position"].iloc[-1])
            gap_pct  = (sigs["ma_short"].iloc[-1] - sigs["ma_long"].iloc[-1]) / sigs["ma_long"].iloc[-1] * 100
            log.debug(f"{sym} gap={gap_pct:+.3f}% sig={last_sig} qty_cur={trader.portfolio.positions.get(sym, {}).get('quantity', 0)}")

        # 4.  Telemetry & equity logging ---------------------------
        stats = trader.portfolio.mark_to_market(last_px)
        stats["realised_pnl"] = getattr(trader.portfolio, "realised_pnl", 0.0)

        history.append(stats["u_pnl"] + stats["realised_pnl"])
        log_equity(**stats)        #append to CSV

        # --- auto-plot equity once every 96 cycles ≈ 24 min at 15-s interval
        if len(history) % 96 == 0:
            from src.plots import save_equity_curve
            save_equity_curve(history, datetime.utcnow().date().isoformat())                     

        if dash is not None:                              # Rich dashboard
            dash.update(stats, trader.portfolio.positions)
        else:                                             # plain console
            print(
                f"💹  Gross ${stats['gross']:,.0f} | "
                f"U-PnL {stats['u_pnl']:+,.0f} | "
                f"R-PnL {stats['realised_pnl']:+,.0f} | "
                f"Risk@Stop ${stats['risk']:,.0f}"
            )

        print(
            f"⏱  Cycle complete at {time.strftime('%Y-%m-%d %H:%M:%S')}, "
            f"waiting {interval}s…"
        )

    # ── schedule & keep main thread alive ─────────────────────────
    th = schedule_task(one_cycle, timedelta(seconds=interval))
    try:
        while th.is_alive():
            th.join(1)
    except KeyboardInterrupt:
        print("🛑  Stopping paper trading.")

    
# ────────────────────────────────────────────────────────────────────────
# CLI entry-point  (matches src/cli.py)
# ────────────────────────────────────────────────────────────────────────
def main(args: List[str] | None = None) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True, help="Comma-separated list (e.g. SPY,QQQ)")
    p.add_argument("--short", type=int, default=10)
    p.add_argument("--long", type=int, default=50)
    p.add_argument("--timeframe", default="1Day")
    p.add_argument("--interval", type=int, default=60)
    p.add_argument("--live", action="store_true",
                   help="Send paper-account orders to Alpaca (not just sim)")

    ns = p.parse_args(args)

    symbols = [norm_sym(s) for s in ns.symbol.split(",")]
    run(symbols, ns.short, ns.long, ns.timeframe, ns.interval, live=ns.live)


if __name__ == "__main__":
    main()

