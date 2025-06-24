# src/signals.py

import pandas as pd


def compute_signals(
    prices: pd.DataFrame, short_window: int, long_window: int
) -> pd.DataFrame:
    """
    Given a DataFrame of historical prices (with a 'close' column),
    compute moving‐average crossover signals.

    Returns a copy of `prices` with three new columns:
      - 'ma_short': rolling short_window simple moving average
      - 'ma_long':  rolling long_window simple moving average
      - 'signal':   +1 when ma_short > ma_long, 0 otherwise
    """
    df = prices.copy()
    df["ma_short"] = df["close"].rolling(short_window).mean()
    df["ma_long"] = df["close"].rolling(long_window).mean()

    # signal: 1 when short MA exceeds long, else 0
    df["signal"] = (df["ma_short"] > df["ma_long"]).astype(int)

    return df
