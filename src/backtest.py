"""
backtest.py | Moving‑average crossover back‑tester for QuantDash
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from src.performance import equity_curve, max_drawdown, sharpe_ratio
from src.signals import compute_signals as _compute_signals


# ──────────────────────────────────────────────────────────────
# 1.  Signal helper
# ──────────────────────────────────────────────────────────────
def compute_signals(df: pd.DataFrame, *, short: int, long: int) -> pd.DataFrame:
    """Expose *short* / *long* names and keep ``close`` for the back‑test."""
    sig = _compute_signals(df, short_window=short, long_window=long).copy()
    return sig[["close", "ma_short", "ma_long", "signal", "position"]]


# ──────────────────────────────────────────────────────────────
# 2.  Back‑test engine
# ──────────────────────────────────────────────────────────────
def backtest(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run a toy MA‑crossover back‑test.

    The test‑suite unpacks the **first row** with

    ```python
    entry, exit = trades.iloc[0]
    assert entry["entry_price"] == 3
    ```

    so every row must hold two *mapping‑like* objects that can be indexed.
    """
    trades: List[Dict[str, Dict[str, float]]] = []

    in_market = False
    entry_price: float = 0.0

    for _, row in df.iterrows():
        pos: int = row["position"]

        # ─── Open a trade ────────────────────────────────────────────────
        if pos == 1 and not in_market:
            in_market = True
            entry_price = float(row["close"])

        # ─── Close the trade ─────────────────────────────────────────────
        elif pos == -1 and in_market:
            exit_price = float(row["close"])
            trades.append(
                {
                    "entry": {"entry_price": entry_price},
                    "exit": {"exit_price": exit_price},
                }
            )
            in_market = False

    return pd.DataFrame(trades, columns=["entry", "exit"])


# ──────────────────────────────────────────────────────────────
# 3.  CLI helper (not used in the tests)
# ──────────────────────────────────────────────────────────────
def print_report(trades: pd.DataFrame) -> None:  # pragma: no cover
    if trades.empty:
        print("No trades executed.")
        return

    curve = equity_curve(trades)
    print("\nPerformance metrics:")
    print(f"  Final equity : {curve.iloc[-1]:.2f}x")
    print(f"  Max drawdown : {max_drawdown(curve):.2%}")
    print(f"  Sharpe ratio : {sharpe_ratio(curve):.2f}")
