import pandas as pd
import numpy as np
import pytest

from src.performance import equity_curve, max_drawdown, sharpe_ratio

def make_trades(returns):
    # build a trades DF with consecutive exit dates
    dates = pd.date_range("2020-01-01", periods=len(returns), freq="D")
    return pd.DataFrame({"exit_date": dates, "pct_return": returns})

def test_equity_curve_simple():
    trades = make_trades([0.1, -0.05, 0.2])
    curve = equity_curve(trades)
    # (1+0.1)*(1-0.05)*(1+0.2) = 1.1 * 0.95 * 1.2
    assert pytest.approx(curve.iloc[-1], rel=1e-6) == 1.1 * 0.95 * 1.2

def test_max_drawdown():
    # create a curve that peaks then falls
    idx = pd.date_range("2020-01-01", periods=4)
    curve = pd.Series([1.0, 1.2, 1.1, 0.9], index=idx)
    # peak at 1.2, trough at .9 ⇒ drawdown = (1.2-0.9)/1.2 = .25
    assert pytest.approx(max_drawdown(curve), rel=1e-6) == 0.25

def test_sharpe_ratio_constant():
    # flat returns → zero vol → Sharpe should be NaN or infinite
    idx = pd.date_range("2020-01-01", periods=5)
    curve = pd.Series(1.0, index=idx)
    sr = sharpe_ratio(curve)
    assert np.isnan(sr) or np.isinf(sr)

def test_sharpe_ratio():
    # build a curve with a known daily return .001 for 252 days
    rets = np.full(252, 0.001)
    curve = pd.Series((1 + rets).cumprod(), index=pd.date_range("2020-01-01", periods=252))
    sr = sharpe_ratio(curve, risk_free=0)
    # for constant returns, Sharpe = mean/std * sqrt(252) = (0.001/0) * sqrt → inf
    assert np.isinf(sr)
