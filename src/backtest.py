"""
backtest.py | Simple moving-average back-tester for QuantDash
"""

from __future__ import annotations

from typing import List

import pandas as pd

from src.performance import equity_curve, max_drawdown, sharpe_ratio
from src.signals import compute_signals as _compute_signals


# ──────────────────────────────────────────────────────────────────────────────
# Signal helpers
# ──────────────────────────────────────────────────────────────────────────────
def compute_signals(df: pd.DataFrame, *, short: int, long: int) -> pd.DataFrame:
    """
    Thin wrapper around ``src.signals.compute_signals`` that matches the
    *short/long* keyword names used in the test-suite.
    """
    sig = _compute_signals(df, short_window=short, long_window=long).copy()
    # the tests only check these four columns
    return sig[["ma_short", "ma_long", "signal", "position"]]


# ──────────────────────────────────────────────────────────────────────────────
# Back-test engine
# ──────────────────────────────────────────────────────────────────────────────
def backtest(df: pd.DataFrame) -> pd.DataFrame:
    """
    Toy back-tester:

    • *df* must contain ``timestamp`` index, ``close`` price,
      and a **position** column that switches +1 → -1.
    • Uses **100 % notional** per position (no sizing logic).
    • Returns a DataFrame of completed trades.
    """
    open_pos = False
    entry_price = 0.0
    entry_time = pd.Timestamp.min
    trades: List[dict] = []

    for ts, row in df.iterrows():
        pos = row["position"]

        if pos == 1 and not open_pos:  # enter long
            open_pos = True
            entry_price = row["close"]
            entry_time = ts
        elif pos == -1 and open_pos:  # exit
            exit_price = row["close"]
            trades.append(
                {
                    "entry_time": entry_time,
                    "exit_time": ts,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pl_pct": exit_price / entry_price - 1.0,
                }
            )
            open_pos = False

    return pd.DataFrame(trades)


# ──────────────────────────────────────────────────────────────────────────────
# Convenience CLI report
# ──────────────────────────────────────────────────────────────────────────────
def print_report(trades: pd.DataFrame) -> None:  # pragma: no cover
    if trades.empty:
        print("No trades executed.")
        return

    curve = equity_curve(trades)
    print("\nPerformance metrics:")
    print(f"  Final equity : {curve.iloc[-1]:.2f}x")
    print(f"  Max drawdown : {max_drawdown(curve):.2%}")
    print(f"  Sharpe ratio : {sharpe_ratio(curve):.2f}")
