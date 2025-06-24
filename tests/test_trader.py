import pytest
from unittest.mock import MagicMock, patch
from src.trader import Trader


@pytest.fixture(autouse=True)
def fake_env(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "key")
    monkeypatch.setenv("ALPACA_API_SECRET", "secret")


@patch("src.trader.TradingClient")
def test_buy_calls_submit_order(fake_client_cls):
    fake_client = MagicMock()
    fake_client_cls.return_value = fake_client

    t = Trader()
    t.buy("AAPL", qty=5)

    # Assert that submit_order was called exactly once:
    assert fake_client.submit_order.call_count == 1
    args, _ = fake_client.submit_order.call_args
    order = args[0]
    assert order.symbol == "AAPL"
    assert order.qty == 5
    assert order.side.name == "BUY"


@patch("src.trader.TradingClient")
def test_sell_calls_submit_order(fake_client_cls):
    fake_client = MagicMock()
    fake_client_cls.return_value = fake_client

    t = Trader()
    t.sell("GOOG", qty=2)

    assert fake_client.submit_order.call_count == 1
    args, _ = fake_client.submit_order.call_args
    order = args[0]
    assert order.symbol == "GOOG"
    assert order.qty == 2
    assert order.side.name == "SELL"
