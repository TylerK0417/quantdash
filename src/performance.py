import pandas as pd
import numpy as np


def equity_curve(trades: pd.DataFrame) -> pd.Series:
    """
    Given a DataFrame with 'exit_date' and 'pct_return',
    return a time‐indexed equity curve (cumulative returns).
    """
    # Sort trades by exit_date
    df = trades.sort_values("exit_date").set_index("exit_date")
    # cumulative product of (1 + return)
    return (1 + df["pct_return"]).cumprod()


def max_drawdown(curve: pd.Series) -> float:
    """
    Compute the maximum drawdown of an equity curve.
    Returns the largest peak-to-trough decline (positive number).
    """
    peak = curve.cummax()
    drawdown = (peak - curve) / peak
    return drawdown.max()


def sharpe_ratio(curve: pd.Series, risk_free: float = 0.0) -> float:
    """
    Annualized Sharpe ratio assuming daily returns in equity curve series.
    risk_free is the annual risk‐free rate (e.g. 0.01 for 1%).
    """
    # daily returns
    rets = curve.pct_change().dropna()
    excess = rets - (risk_free / 252)
    return (excess.mean() / excess.std()) * np.sqrt(252)
