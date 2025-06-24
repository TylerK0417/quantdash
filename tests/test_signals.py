import pandas as pd
import pytest
from src.signals import compute_signals


def test_signal_columns():
    """
    compute_signals should add 'ma_short', 'ma_long', and 'signal' columns.
    """
    prices = pd.DataFrame({"close": [1, 2, 3, 2, 1]})
    df = compute_signals(prices, short_window=2, long_window=3)
    for col in ("ma_short", "ma_long", "signal"):
        assert col in df.columns


def test_signal_values():
    """
    On the third row (index 2):
      ma_short = (2+3)/2 = 2.5
      ma_long  = (1+2+3)/3 = 2.0
      signal   = 1 (since 2.5 > 2.0)

    On the last row:
      signal should be 0.
    """
    prices = pd.DataFrame({"close": [1, 2, 3, 2, 1]})
    df = compute_signals(prices, short_window=2, long_window=3)

    # Check MA values
    assert pytest.approx(df["ma_short"].iloc[2], rel=1e-6) == 2.5
    assert pytest.approx(df["ma_long"].iloc[2], rel=1e-6) == 2.0

    # Check signal logic
    assert df["signal"].iloc[2] == 1
    assert df["signal"].iloc[-1] == 0
