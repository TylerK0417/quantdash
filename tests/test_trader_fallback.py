# tests/test_trader_fallback.py
"""
Validate that Trader._submit():        (a) posts exactly one LIMIT order,
(b) cancels it after `limit_timeout`, and (c) submits one MARKET order
for the unfilled remainder – never over-buying or duplicating size.
"""

import types
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from src.trader import Trader, OrderSide


@pytest.fixture(autouse=True)
def fake_env(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "key")
    monkeypatch.setenv("ALPACA_API_SECRET", "secret")


# ---------------------------------------------------------------------- #
# Utility helpers
# ---------------------------------------------------------------------- #
def make_order(status: str, filled_qty: int = 0, order_id="OID") -> object:
    """
    Return a minimal object that looks like an Alpaca Order for the
    attributes _submit() accesses.
    """
    return types.SimpleNamespace(
        id=order_id,
        status=status,
        filled_qty=str(filled_qty),
        limit_price=100.0,
        side="buy",
        symbol="AAPL",
    )


class StubClient(MagicMock):
    """
    Acts like MagicMock *but* its class name is not 'MagicMock', so the
    early-return guard in Trader._submit() is bypassed.
    """
    pass


# ---------------------------------------------------------------------- #
# The actual test
# ---------------------------------------------------------------------- #
@patch('time.sleep')  # Mock sleep to make test fast
@patch('time.monotonic')  # Mock monotonic to control timeouts
def test_limit_timeout_then_market(mock_monotonic, mock_sleep):
    # ---- 1. Build stubbed Trader ------------------------------------
    # Control time progression to match test expectations:
    # - limit_timeout = 1.0, need 2 polls → times 0, 0, 0.4, 0.8, 1.2 (exit)
    # - cancel_timeout = 0.5, need 2 polls → times 1.2, 1.2, 1.35, 1.45, 1.8 (exit)
    time_seq = [
        0,    # deadline calc for limit wait
        0,    # first poll check
        0.4,  # second poll check
        0.8,  # third poll check
        1.2,  # timeout - exit limit wait
        1.2,  # deadline calc for cancel wait
        1.2,  # first poll check
        1.35, # second poll check
        1.45, # third poll check
        1.8,  # timeout - exit cancel wait
        2.0,  # market fallback time
    ]
    mock_monotonic.side_effect = time_seq

    mock_client = StubClient()
    trader = Trader(
        paper=False,           # pretend live mode
        limit_timeout=1,       # 1 s timeout to keep test fast
        cancel_timeout=0.5,
    )
    trader.client = mock_client       # inject stub client
    trader._open_cache = set()  

    # ---- 2. Mock client behaviour -----------------------------------
    limit_order   = make_order("new", 0, order_id="LIM1")
    partial_fill  = make_order("partially_filled", 3, "LIM1")
    canceled      = make_order("canceled", 3, "LIM1")
    market_order  = make_order("filled", 2, order_id="MKT1")

    # First call to submit_order returns LIMIT; second returns MARKET
    mock_client.submit_order.side_effect = [limit_order, market_order]

    # get_order cycles through states (called multiple times by _submit)
    mock_client.get_order.side_effect = [
        limit_order, limit_order,          # before timeout
        partial_fill,                      # just before cancel
        partial_fill, canceled,            # after cancel
        market_order,                      # after MARKET
    ]

    # cancel_order returns a response with .status_code == 204
    mock_client.cancel_order.return_value = types.SimpleNamespace(status_code=204)

    # get_clock returns market is open (so MARKET fallback proceeds)
    mock_client.get_clock.return_value = types.SimpleNamespace(is_open=True)

    # ---- 3. Call the method under test ------------------------------
    trader._submit(OrderSide.BUY, "AAPL", qty=5, price=100.0, atr_val=1.0)

    # ---- 4. Assertions ---------------------------------------------
    # LIMIT + MARKET only → exactly 2 submits
    assert mock_client.submit_order.call_count == 2

    # ---- check the qty values inside the request objects ------------
    limit_call, market_call = mock_client.submit_order.call_args_list
    limit_req  = limit_call.args[0]      # first positional arg
    market_req = market_call.args[0]

    assert getattr(limit_req,  "qty") == 5     # full size
    assert getattr(market_req, "qty") == 2     # remainder (5-3)


    # cancel_order called exactly once, with original LIMIT ID
    mock_client.cancel_order.assert_called_once_with("LIM1")
