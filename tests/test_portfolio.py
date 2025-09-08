# ────────────────────── tests/test_portfolio.py ────────────────────────
import pandas as pd
from unittest.mock import MagicMock, patch

from src.portfolio import Portfolio
from src.trader import Trader


@patch("src.trader.TradingClient")  # stub network calls
def test_portfolio_round_trip(fake_client_cls):
    fake_client_cls.return_value = MagicMock()

    port = Portfolio(cash=10_000)
    trader = Trader(paper=True, portfolio=port)

    # BUY signal
    df_buy = pd.DataFrame({"close": [100], "position": [1]})
    trader.execute_signals("FOO", df_buy)
    assert port.has_position("FOO")

    # SELL signal
    df_sell = pd.DataFrame({"close": [110], "position": [-1]})
    trader.execute_signals("FOO", df_sell)
    assert not port.has_position("FOO")
    assert port.realised_pnl == 10 * port.max_risk_per_trade * 10  # profit positive
