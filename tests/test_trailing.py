import pandas as pd
from src.portfolio import Portfolio
from src.trader import Trader

def test_trailing_ratchets():
    port = Portfolio()
    trader = Trader(paper=True, portfolio=port)

    # open a dummy long
    port.open_position("FOO", qty=1, price=100, stop=95)

    # fake OHLC with rising closes
    closes = [101, 103, 106]
    for c in closes:
        df = pd.DataFrame({"high": [c], "low": [c], "close": [c]})
        trader.update_trailing({"FOO": c}, {"FOO": df})

    pos = port.positions["FOO"]
    assert pos["trail_base"] == 106        # ratcheted to last high
    assert pos["stop"] > 95                # stop moved upward
