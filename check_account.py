# check_account.py
from dotenv import load_dotenv
import os, sys

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

# 1. Load your .env
load_dotenv()

KEY    = os.getenv("ALPACA_API_KEY")
SECRET = os.getenv("ALPACA_API_SECRET")

if not KEY or not SECRET:
    print("❌ ALPACA_API_KEY or SECRET not set in .env")
    sys.exit(1)

# 2. Initialize the paper client
cli = TradingClient(KEY, SECRET, paper=True)

# 3. Clock
try:
    clock = cli.get_clock()
    print("▶ Market open? ", clock.is_open, "   Next open:", clock.next_open)
except Exception as e:
    print("⚠️  Could not fetch clock:", e)

# 4. Account
try:
    acct = cli.get_account()
    print("▶ Account status:", acct.status)
    print("  Cash:          ", acct.cash)
    print("  Buying Power:  ", acct.buying_power)
except Exception as e:
    print("⚠️  Could not fetch account:", e)

# 5. Open orders (uses get_orders, not list_orders)
try:
    open_orders = cli.get_orders(status="open")
    print(f"▶ Open orders ({len(open_orders)}):")
    for o in open_orders:
        print(f"   • {o.id}  {o.symbol}  {o.side}  qty={o.qty}  status={o.status}")
except Exception as e:
    print("⚠️  Could not fetch open orders:", e)

# 6. Submit a 1-share test order
print("▶ Submitting a test MARKET order for 1 AAPL …")
try:
    test = MarketOrderRequest(
        symbol="AAPL",
        qty=1,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
    )
    resp = cli.submit_order(test)
    print("✅ Test order succeeded, id=", resp.id)
except Exception as e:
    print("❌ Test order failed:", e)
