"""
backtest.py | Simple MA Crossover Back-tester for QuantDash

Usage:
    python -m src.backtest --symbol SPY --short 10 --long 50
"""

import os
import argparse
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

# Import the shared MA logic under a private name
from src.signals import compute_signals as _compute_signals

# Where our Parquet lives
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def load_data(symbol: str) -> pd.DataFrame:
    """
    Load the daily bars Parquet into a DataFrame,
    indexed by timestamp and sorted ascending.
    """
    path = DATA_DIR / f"{symbol}_1Day.parquet"
    df = pd.read_parquet(path)
    df = df.set_index("timestamp").sort_index()
    return df


def compute_signals(
    df: pd.DataFrame,
    short: int,
    long: int
) -> pd.DataFrame:
    """
    Wrapper around src.signals.compute_signals that accepts
    the keywords 'short' and 'long' to match test expectations.

    Returns a DataFrame with columns:
      - ma_short, ma_long, signal, position
    """
    # Delegate to the real implementation
    sig = _compute_signals(df, short_window=short, long_window=long)

    # Ensure we have 'position' too (diff of signal)
    if "position" not in sig.columns:
        sig["position"] = sig["signal"].diff().fillna(0).astype(int)

    return sig


def backtest(df: pd.DataFrame) -> pd.DataFrame:
    """
    Walk through 'position':
      - entry when position == 1
      - exit  when position == -1
    Record each trade's entry_date, exit_date, prices, and pct_return.
    """
    trades = []
    entry_price = None
    entry_date = None

    for date, row in df.iterrows():
        pos = row["position"]
        price = row["close"]

        # Open a trade
        if pos == 1:
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
            entry_price = None  # reset

    return pd.DataFrame(trades)


def main():
    load_dotenv()  # pick up ALPACA keys if you extend this

    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True, help="Ticker, e.g. SPY")
    p.add_argument("--short",  type=int, default=10, help="Short MA window")
    p.add_argument("--long",   type=int, default=50, help="Long MA window")
    args = p.parse_args()

    # 1) Load & signal
    df = load_data(args.symbol)
    sig = compute_signals(df, args.short, args.long)
    trades = backtest(sig)

    # 2) Summary
    print(f"\n=== {args.symbol} MA{args.short}/{args.long} Crossover ===")
    print(f"Total trades: {len(trades)}")

    # 3) Handle no-trade edge case
    if trades.empty:
        print("⚠️  No trades generated — try a shorter window or more history")
        return

    # 4) Otherwise, show stats & table
    avg_ret = trades["pct_return"].mean()
    print(f"Avg return: {avg_ret:.2%}")
    print(trades.to_string(index=False))


if __name__ == "__main__":
    main()
