# src/performance.py
"""
Performance utilities:
- equity_curve    : cumulative growth of $1 from a trades DataFrame
- max_drawdown    : worst peak-to-trough drawdown (positive fraction)
- sharpe_ratio    : annualised risk-adjusted return
- report          : pretty-print all of the above
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EPS = 1e-10  # tiny number to detect “zero”


def equity_curve(trades: pd.DataFrame) -> pd.Series:
    """
    Build a $-1 equity curve from a trades DataFrame containing
      - exit_date   datetime64[ns]
      - pct_return  float (decimal, e.g. +0.05)
    Returns a pd.Series indexed by exit_date.
    """
    curve = (1 + trades["pct_return"]).cumprod()
    curve.index = pd.to_datetime(trades["exit_date"])
    return curve


def max_drawdown(curve: pd.Series) -> float:
    """
    Return the maximum drawdown as a positive fraction.
    E.g. a drop from 1.2 to 0.9 ⇒ (1.2−0.9)/1.2 = 0.25.
    """
    peak = curve.cummax()
    draw = (peak - curve) / peak
    return float(draw.max())


def sharpe_ratio(curve: pd.Series, *, risk_free: float = 0.0) -> float:
    """
    Annualised Sharpe ratio of an equity curve.
      • Flat curve (all 0% daily)         → NaN
      • Constant non-zero daily returns   → ±∞
    """
    # compute daily returns, fill first NaN with 0
    daily  = curve.pct_change().fillna(0.0)
    excess = daily - (risk_free / 252.0)

    # if all non-zero returns are identical ⇒ infinite Sharpe
    if excess.iloc[1:].abs().nunique() <= 1:
        mu = excess.mean()
        if abs(mu) < EPS:
            return float("nan")
        return np.inf * np.sign(mu)

    sigma = excess.std()
    if sigma < EPS:
        return float("nan")
    return float((excess.mean() / sigma) * np.sqrt(252))


def report(trades: pd.DataFrame) -> None:
    """
    Print equity curve, max drawdown, and Sharpe for a backtest.
    """
    eq = equity_curve(trades)
    md = max_drawdown(eq)
    sr = sharpe_ratio(eq)

    print("\n=== Performance ===")
    print("Equity curve:")
    print(eq.to_string())
    print(f"Max drawdown: {md:.2%}")
    print(f"Sharpe ratio: {sr:.4f}")
