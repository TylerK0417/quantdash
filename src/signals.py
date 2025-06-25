"""
signals.py | SMA‑crossover signal generator for QuantDash
"""

from __future__ import annotations

import pandas as pd


def compute_signals(
    df: pd.DataFrame,
    short: int | None = None,
    long: int | None = None,
    *,
    short_window: int | None = None,
    long_window: int | None = None,
) -> pd.DataFrame:
    """
    Calculate simple‑moving‑average crossover signals.

    Accepts either `(short, long)` **or** the legacy
    `(short_window, long_window)` used in existing tests.

    Returns a DataFrame with columns

    ─ ma_short, ma_long
    ─ signal     : 1 only on an upward crossover, else 0
    ─ position   : 1 on the **buy** event, ‑1 on the **sell** event, 0 otherwise
                   (this is exactly what the tests expect)
    """
    # ────────────────── harmonise arg names ──────────────────
    short = short if short is not None else short_window
    long = long if long is not None else long_window
    if short is None or long is None:
        raise ValueError("Must supply short & long window sizes")

    out = df.copy()

    # ────────────────── moving averages ──────────────────
    out["ma_short"] = out["close"].rolling(short, min_periods=1).mean()
    out["ma_long"] = out["close"].rolling(long, min_periods=1).mean()

    # ────────────────── crossover detection ──────────────────
    crossed_up = (out["ma_short"] > out["ma_long"]) & (
        out["ma_short"].shift(1) <= out["ma_long"].shift(1)
    )
    crossed_dn = (out["ma_short"] < out["ma_long"]) & (
        out["ma_short"].shift(1) >= out["ma_long"].shift(1)
    )

    # signal = 1 only on upward cross
    out["signal"] = crossed_up.astype(int)

    # position events: +1 on buy, ‑1 on sell, 0 otherwise
    out["position"] = 0
    out.loc[crossed_up, "position"] = 1
    out.loc[crossed_dn, "position"] = -1

    return out[["close", "ma_short", "ma_long", "signal", "position"]]
