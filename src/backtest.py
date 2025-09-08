# src/backtest.py

"""
backtest.py | Simple MA Crossover Back-tester for QuantDash

Usage:
    qdash backtest --symbol SPY --short 10 --long 50
"""

import argparse
import pandas as pd
from src.download import load_data
from src.signals import compute_signals

def backtest(df: pd.DataFrame) -> pd.DataFrame:
    """
    Walk through the 'position' column:
      - entry when position == 1
      - exit when position == -1
    Record each trade's entry_date, exit_date, prices, and pct_return.
    """
    trades = []
    entry_price = None
    entry_date = None

    for date, row in df.iterrows():
        pos = row["position"]
        price = row["close"]

        # Open a trade
        if pos == 1 and entry_price is None:
            entry_price = price
            entry_date = date

        # Close a trade
        elif pos == -1 and entry_price is not None:
            exit_price = price
            exit_date = date
            pct_ret = (exit_price / entry_price) - 1
            trades.append({
                "entry_date":  entry_date,
                "exit_date":   exit_date,
                "entry_price": entry_price,
                "exit_price":  exit_price,
                "pct_return":  pct_ret,
            })
            entry_price = None  # reset for next trade

    return pd.DataFrame(trades)

def main(args=None):
    """
    CLI entrypoint for backtesting.
    Accepts an optional list of strings `args` for testing/CLI wrappers.
    """
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True, help="Ticker, e.g. SPY")
    p.add_argument("--short",  type=int, default=10, help="Short MA window")
    p.add_argument("--long",   type=int, default=50, help="Long MA window")
    ns = p.parse_args(args)

    # 1) Load & signal
    df = load_data(ns.symbol)
    sig = compute_signals(df, ns.short, ns.long)

    # 2) Run backtest
    trades = backtest(sig)

    # 3) Summary
    print(f"\n=== {ns.symbol} MA{ns.short}/{ns.long} Crossover ===")
    print(f"Total trades: {len(trades)}")

    # 4) No-trade edge case
    if trades.empty:
        print("⚠️  No trades generated — try a shorter window or more history")
        return

    # 5) Stats & table
    avg_ret = trades["pct_return"].mean()
    print(f"Avg return: {avg_ret:.2%}")
    print(trades.to_string(index=False))


if __name__ == "__main__":
    main()
