# src/paper.py

import argparse
import time
from datetime import timedelta

from src.download import load_data
from src.backtest import compute_signals
from src.trader import Trader
from src.scheduler import schedule_task


def run(symbol: str, short: int, long: int, paper: bool):
    """
    1) load bars
    2) compute MA crossover signals
    3) send them to Trader (paper mode)
    """
    df = load_data(symbol)
    df_sigs = compute_signals(df, short, long)
    trader = Trader(paper=paper)
    trader.execute_signals(df_sigs)


def main():
    p = argparse.ArgumentParser(
        prog="python -m src.paper",
        description="Continuously run a paper‐trading loop on a schedule",
    )
    p.add_argument("--symbol", required=True, help="Ticker to trade (e.g. SPY)")
    p.add_argument("--short", type=int, required=True, help="Short MA window")
    p.add_argument("--long", type=int, required=True, help="Long MA window")
    p.add_argument(
        "--interval",
        type=float,
        default=60,
        help="Seconds between each run (default: 60s)",
    )
    args = p.parse_args()

    # schedule the job to re‐run forever
    schedule_task(
        lambda: run(args.symbol, args.short, args.long, paper=True),
        timedelta(seconds=args.interval),
    )

    # keep the script alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹️  Stopping paper‐trading loop.")


if __name__ == "__main__":
    main()
