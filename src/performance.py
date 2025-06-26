# src/performance.py
"""
Performance utilities:
- equity_curve : cumulative growth of $1
- max_drawdown : worst peak‑to‑trough decline
- sharpe_ratio : annualised risk‑adjusted return
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EPS = 1e-10  # numerical zero


# ----------------------------------------------------------------------
# Equity curve & draw‑down
# ----------------------------------------------------------------------
def equity_curve(trades: pd.DataFrame) -> pd.Series:
    """
    Build a $‑1 equity curve from a trades DataFrame that contains

        exit_date   datetime64[ns]
        pct_return  float (decimal, e.g. +0.05)

    The index of the returned Series is the exit_date.
    """
    curve = (1 + trades["pct_return"]).cumprod()
    curve.index = pd.to_datetime(trades["exit_date"])
    return curve


def max_drawdown(curve: pd.Series) -> float:
    """
    Return *positive* fractional draw‑down. 0.25 ⇒ ‑25 %.
    """
    peak = curve.cummax()
    draw = (peak - curve) / peak
    return draw.max()


# ----------------------------------------------------------------------
# Sharpe ratio
# ----------------------------------------------------------------------
def sharpe_ratio(curve: pd.Series, *, risk_free: float = 0.0) -> float:
    """
    Annualised Sharpe ratio of an equity curve.

    Special cases
    -------------
    • Flat curve (all returns 0)              → NaN
    • Constant non‑zero daily returns         → ±∞
    """
    # daily % returns; first value becomes 0 after fillna
    daily = curve.pct_change().fillna(0.0)
    excess = daily - (risk_free / 252.0)

    # Detect “constant” returns (ignoring the first 0)
    if excess.iloc[1:].abs().nunique() <= 1:  # all identical
        mu = excess.mean()
        if abs(mu) < EPS:  # exactly flat → undefined
            return float("nan")
        return np.inf * np.sign(mu)  # constant +ve / ‑ve

    # Standard Sharpe
    sigma = excess.std()
    if sigma < EPS:
        return float("nan")  # should only happen for flat

    return (excess.mean() / sigma) * np.sqrt(252)
