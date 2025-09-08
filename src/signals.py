# ── src/signals.py ────────────────────────────────────────────────────
from __future__ import annotations

import pandas as pd


def compute_signals(
    df: pd.DataFrame,
    short: int | None = None,
    long: int | None = None,
    *,
    short_window: int | None = None,   # ↔ legacy arg
    long_window: int | None = None,    # ↔ legacy arg
    thresh_pct: float = 0.0,           # ← NEW (± % gap that triggers)
) -> pd.DataFrame:
    """
    Simple-moving-average crossover with optional *gap threshold*.

    Call patterns (all valid):

        compute_signals(df, short=5, long=20)
        compute_signals(df, short_window=5, long_window=20)
        compute_signals(df, short=3, long=9, thresh_pct=0.02)

    Returns a DataFrame with exactly these columns, in order:
      • close
      • ma_short
      • ma_long
      • signal     (1 on upward cross, else 0)
      • position   (1 buy row, −1 sell row, 0 otherwise; forward-filled)
    """
    # ── 1. normalise arg names ─────────────────────────────────────────
    if short is None and short_window is None:
        raise ValueError("Must supply short window size")
    if long is None and long_window is None:
        raise ValueError("Must supply long window size")

    short = short if short is not None else short_window  # type: ignore
    long  = long  if long  is not None else long_window   # type: ignore

    # ── 2. compute moving averages ────────────────────────────────────
    out = df.copy()
    out["ma_short"] = out["close"].rolling(short, min_periods=1).mean()
    out["ma_long"]  = out["close"].rolling(long,  min_periods=1).mean()

    # ── 3. gap (%) helper when threshold > 0 ──────────────────────────
    gap = (out["ma_short"] - out["ma_long"]) / out["ma_long"] * 100

    # ── 4. detect crosses (with or without threshold) ────────────────
    if thresh_pct == 0:
        crossed_up = (out["ma_short"] > out["ma_long"]) & (
            out["ma_short"].shift(1) <= out["ma_long"].shift(1)
        )
        crossed_dn = (out["ma_short"] < out["ma_long"]) & (
            out["ma_short"].shift(1) >= out["ma_long"].shift(1)
        )
    else:
        crossed_up = (gap > +thresh_pct) & (gap.shift(1) <= +thresh_pct)
        crossed_dn = (gap < -thresh_pct) & (gap.shift(1) >= -thresh_pct)

    # ── 5. build output columns ───────────────────────────────────────
    out["signal"]   = crossed_up.astype(int)
    out["position"] = 0
    out.loc[crossed_up, "position"] = 1
    out.loc[crossed_dn, "position"] = -1
    out["position"] = out["position"].ffill()

    return out[["close", "ma_short", "ma_long", "signal", "position"]]
