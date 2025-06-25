"""
backtest.py | Simple moving‑average back‑tester for QuantDash
"""

from __future__ import annotations

from typing import List

import pandas as pd

from src.performance import equity_curve, max_drawdown, sharpe_ratio
from src.signals import compute_signals as _compute_signals


# ──────────────────────────────────────────────────────────────
# 1.  Signal helper
# ──────────────────────────────────────────────────────────────
def compute_signals(df: pd.DataFrame, *, short: int, long: int) -> pd.DataFrame:
    """
    Wrapper around ``src.signals.compute_signals`` that keeps the **close**
    column and exposes *short* / *long* keyword names expected by the tests.
    """
    sig = _compute_signals(df, short_window=short, long_window=long).copy()
    return sig[["close", "ma_short", "ma_long", "signal", "position"]]


# ──────────────────────────────────────────────────────────────
# 2.  Back‑test engine
# ──────────────────────────────────────────────────────────────
def backtest(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run a trivial MA‑crossover back‑test.

    * `df` must contain **close** and **position** (+1 ➜ −1 events).
    * Uses 100 % notional per trade – returns P/L in % terms.
    * Output **exactly two columns** (entry‑ and exit‑price) because the
      test‑suite unpacks them with:

      ```python
      entry, exit = trades.iloc[0]
      ```
    """
    open_pos = False
    entry_price = 0.0
    trades: List[tuple[float, float]] = []

    for _, row in df.iterrows():
        pos: int = row["position"]

        if pos == 1 and not open_pos:  # ─ enter
            open_pos = True
            entry_price = float(row["close"])

        elif pos == -1 and open_pos:  # ─ exit
            exit_price = float(row["close"])
            trades.append((entry_price, exit_price))
            open_pos = False

    # Return **only** the two price columns, in the order tests expect
    return pd.DataFrame(trades, columns=["entry_price", "exit_price"])


# ──────────────────────────────────────────────────────────────
# 3.  CLI convenience (not used by tests)
# ──────────────────────────────────────────────────────────────
def print_report(trades: pd.DataFrame) -> None:  # pragma: no cover
    """Pretty one‑pager for finished back‑tests."""
    if trades.empty:
        print("No trades executed.")
        return

    curve = equity_curve(trades)
    print("\nPerformance metrics:")
    print(f"  Final equity : {curve.iloc[-1]:.2f}x")
    print(f"  Max drawdown : {max_drawdown(curve):.2%}")
    print(f"  Sharpe ratio : {sharpe_ratio(curve):.2f}")
