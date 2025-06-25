"""
Tests for the backtest module.
"""

import pytest
import pandas as pd

from src.backtest import compute_signals, backtest


def make_df(prices):
    """
    Helper to build a DataFrame of close prices indexed by consecutive dates.
    """
    dates = pd.date_range("2025-01-01", periods=len(prices), freq="D")
    return pd.DataFrame({"close": prices}, index=dates)


def test_compute_signals_columns_and_values():
    """Signals and MA columns are created and have expected values."""
    prices = [1, 2, 3, 2, 1]
    df = make_df(prices)
    sig = compute_signals(df, short=2, long=3)

    # columns exist
    for col in ("ma_short", "ma_long", "signal", "position"):
        assert col in sig.columns

    # specific values on row 2
    assert pytest.approx(sig["ma_short"].iloc[2], rel=1e-6) == 2.5
    assert pytest.approx(sig["ma_long"].iloc[2], rel=1e-6) == 2.0
    assert sig["signal"].iloc[2] == 1

    # last row goes flat → position diff -1
    assert sig["signal"].iloc[-1] == 0
    assert sig["position"].iloc[-1] == -1


def test_backtest_single_trade():
    """Back-test should yield exactly one round-trip trade."""
    prices = [1, 2, 3, 2, 1]
    sig = compute_signals(make_df(prices), short=2, long=3)
    trades = backtest(sig)

    assert len(trades) == 1
    entry, exit = trades.iloc[0]
    assert entry["entry_price"] == 3
    assert exit["exit_price"] == 1
