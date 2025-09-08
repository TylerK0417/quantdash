# tests/test_trader_fallback.py
"""
Validate that Trader._submit():        (a) posts exactly one LIMIT order,
(b) cancels it after `limit_timeout`, and (c) submits one MARKET order
for the unfilled remainder – never over-buying or duplicating size.
"""

import types
from unittest.mock import MagicMock
import pandas as pd

from src.trader import Trader, OrderSide


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
def test_limit_timeout_then_market():
    # ---- 1. Build stubbed Trader ------------------------------------
 
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
