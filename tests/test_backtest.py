import pandas as pd
import pytest
from src.backtest import compute_signals, backtest


def make_df(prices):
    """
    Helper: generate a DataFrame of daily closes from a list of prices,
    indexed by consecutive calendar days starting 2025-01-01.
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

    trade = trades.iloc[0]
    # Check entry/exit dates and prices
    assert trade["entry_date"] == df.index[2]
    assert trade["exit_date"] == df.index[-1]
    assert trade["entry_price"] == 3
    assert trade["exit_price"] == 1

    # Percent return = (1/3) - 1 = -2/3
    expected = (1 / 3) - 1
    assert pytest.approx(trade["pct_return"], rel=1e-6) == expected
