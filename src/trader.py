from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import os
from dotenv import load_dotenv


class Trader:
    def __init__(self, paper: bool = True):
        load_dotenv()
        key = os.environ["ALPACA_API_KEY"]
        secret = os.environ["ALPACA_API_SECRET"]
        self.client = TradingClient(key, secret, paper=paper)

    def buy(self, symbol: str, qty: float):
        """Submit a market buy order for qty shares of symbol."""
        order = MarketOrderRequest(
            symbol=symbol, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC
        )
        return self.client.submit_order(order)

    def sell(self, symbol: str, qty: float):
        """Submit a market sell order for qty shares of symbol."""
        order = MarketOrderRequest(
            symbol=symbol, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.GTC
        )
        return self.client.submit_order(order)
