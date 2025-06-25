# tests/test_performance.py

import numpy as np
import pandas as pd
import pytest

from src.performance import equity_curve, max_drawdown, sharpe_ratio

def test_equity_curve_basic():
    # 10% gain, then 10% gain → 1 → 1.21
    r = pd.Series([0.10, 0.10])
    eq = equity_curve(r, initial_capital=1.0)
    assert np.allclose(eq.values, [1.1, 1.21], rtol=1e-6)

def test_max_drawdown():
    # equity goes up then down 10%, so max drawdown is -0.10
    eq = pd.Series([1.0, 1.1, 0.99, 1.0])
    assert pytest.approx(max_drawdown(eq), rel=1e-6) == -0.10

def test_sharpe_ratio_constant():
    # constant returns → std = 0 → Sharpe should be NaN
    r = pd.Series([0.01, 0.01, 0.01])
    sr = sharpe_ratio(r)
    assert np.isnan(sr)

def test_sharpe_ratio_known():
    # a simple two-day return series: [0, x].
    # Sharpe = mean/std * sqrt(252)
    r = pd.Series([0.0, 0.02])
    expected = (r.mean() / r.std()) * np.sqrt(252)
    assert pytest.approx(sharpe_ratio(r), rel=1e-8) == expected
