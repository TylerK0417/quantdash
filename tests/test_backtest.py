"""
Tests for the backtest module.
"""

import pytest
import pandas as pd
from pathlib import Path
import argparse

from src.backtest import compute_signals, backtest


def make_df(prices):
    """
    Helper to build a DataFrame of close prices indexed by consecutive dates.
    """
    dates = pd.date_range("2025-01-01", periods=len(prices), freq="D")
    return pd.DataFrame({"close": prices}, index=dates)


def test_compute_signals_columns_and_values():
    # Given a simple price sequence that rises then falls,
    # with short=2, long=3, we know exactly when signals flip.
    prices = [1, 2, 3, 2, 1]
    df = make_df(prices)
    sig = compute_signals(df, short=2, long=3)

    # Ensure the MA columns, signal, and position exist
    for col in ("ma_short", "ma_long", "signal", "position"):
        assert col in sig.columns

    # On the 3rd row (index 2), ma_short=(2+3)/2=2.5, ma_long=(1+2+3)/3=2.0 → signal 1
    assert pytest.approx(sig["ma_short"].iloc[2], rel=1e-6) == 2.5
    assert pytest.approx(sig["ma_long"].iloc[2], rel=1e-6) == 2.0
    assert sig["signal"].iloc[2] == 1

    # On the last row, price falls so signal → 0 and position diff → -1
    assert sig["signal"].iloc[-1] == 0
    assert sig["position"].iloc[-1] == -1


def test_backtest_single_trade():
    # Using the same price pattern, backtest() should produce exactly one trade:
    # entry at price=3 on day3, exit at price=1 on day5.
    prices = [1, 2, 3, 2, 1]
    df = make_df(prices)
    sig = compute_signals(df, short=2, long=3)
    trades = backtest(sig)

    # Should be a DataFrame with one row
    assert isinstance(trades, pd.DataFrame)
    assert len(trades) == 1

    # Check entry and exit
    entry, exit = trades.iloc[0]
    assert entry["entry_price"] == 3
    assert exit["exit_price"] == 1


def test_run_submits_two_orders(monkeypatch):
    # GIVEN a price that goes up then down
    df = make_df([1, 2, 3, 2, 1])

    # patch load_data to return our df
    import src.paper as paper_module  # noqa
    monkeypatch.setattr(paper_module, "load_data", lambda symbol: df)

    # patch Trader to use our DummyTrader
    from test_paper import DummyTrader  # noqa
    created = {}

    def fake_trader(paper_flag):
        inst = DummyTrader(paper_flag)
        created["inst"] = inst
        return inst

    monkeypatch.setattr(paper_module, "Trader", fake_trader)

    # WHEN we run with short=2,long=3
    paper_module.run(symbol="FOO", short=2, long=3, paper=True)

    # THEN DummyTrader.execute_signals saw exactly two “orders”
    inst = created["inst"]
    assert inst.paper is True
    assert len(inst.orders) == 2
