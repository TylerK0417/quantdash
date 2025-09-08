# test_seed.py ─ run with:  python test_seed.py
from pprint import pprint

from src.trader import Trader
from src.paper   import _seed_broker_positions   # your helper
from src.download import load_data

# ---- bootstrap like paper.py ------------------------------------------------
t = Trader(paper=True)
_seed_broker_positions(t.portfolio)

print("\n--- portfolio right after seeding ---")
pprint(t.portfolio.positions)            # BTCUSD should be here

# ---- simulate mark-to-market -------------------------------------------------
last_px = {}
try:
    last_px["BTCUSD"] = float(
        load_data("BTCUSD", "1Min")["close"].iloc[-1]
    )
except Exception as exc:
    print("⚠️ could not load price:", exc)

stats = t.portfolio.mark_to_market(last_px)

print("\n--- positions AFTER mark_to_market ---")
pprint(t.portfolio.positions)

print("\n--- stats dict ---")
pprint(stats)
