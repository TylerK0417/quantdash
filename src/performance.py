# src/performance.py

import pandas as pd
import numpy as np

def equity_curve(returns: pd.Series, initial_capital: float = 1.0) -> pd.Series:
    """
    Given a pandas Series of period returns (i.e. 0.02 = +2%),
    compute and return the cumulative equity curve, starting at initial_capital.
    """
    return (1 + returns).cumprod() * initial_capital


def max_drawdown(equity: pd.Series) -> float:
    """
    Given a pandas Series representing an equity curve (e.g. from equity_curve()),
    compute the maximum drawdown (in decimal form, e.g. -0.12 for a 12% drop).
    """
    running_max = equity.cummax()
    drawdowns = equity / running_max - 1
    return drawdowns.min()


def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    trading_days: int = 252
) -> float:
    """
    Compute the annualized Sharpe ratio of a returns series.
    
    Uses pandas.Series.std() (ddof=1) so that a constant series yields NaN.
    Scales by sqrt(trading_days). Defaults to 0% risk-free rate.
    """
    # subtract daily risk-free
    excess = returns - (risk_free_rate / trading_days)
    return (excess.mean() / excess.std()) * np.sqrt(trading_days)
