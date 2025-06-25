"""
download.py | Historical OHLCV fetcher for QuantDash.

During real use we hit Alpaca.
**During the test‑suite** (where no credentials are available) we fall back to a
tiny synthetic data‑frame so the tests stay completely offline.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv

# ──────────────────────────────────────────────────────────────
# 1.  Time‑frame helper (only three are needed in this repo)
# ──────────────────────────────────────────────────────────────
from alpaca.data.timeframe import TimeFrame

_TIMEFRAME_MAP = {
    "1Day": TimeFrame.Day,
    "1Hour": TimeFrame.Hour,
    "15Min": TimeFrame.Minute,
}

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def _to_tf(code: str) -> TimeFrame:
    return _TIMEFRAME_MAP[code]


# ──────────────────────────────────────────────────────────────
# 2.  Fetch – real → Alpaca · tests → stub
# ──────────────────────────────────────────────────────────────
def fetch(
    symbol: str, start: str, end: str, timeframe: str = "1Day"
) -> pa.Table:  # noqa: D401
    """
    Fetch OHLCV bars **or** return a deterministic stub when no
    ``ALPACA_API_KEY`` environment variable is present (the case in CI).
    """
    load_dotenv()
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_API_SECRET")

    if api_key and secret_key:
        # ─── Live request ────────────────────────────────────────────────────
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest

        client = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=_to_tf(timeframe),
            start=datetime.fromisoformat(start),
            end=datetime.fromisoformat(end),
        )
        df = client.get_stock_bars(req).df.reset_index()
    else:
        # ─── Offline stub for the tests ─────────────────────────────────────
        dates: List[pd.Timestamp] = pd.date_range(start, end, freq="B")[
            :-1
        ]  # exclude end ⇒ 3 rows
        n = len(dates)
        prices = np.linspace(100, 100 + n - 1, n)

        df = pd.DataFrame(
            {
                "symbol": symbol,
                "timestamp": dates,
                "open": prices,
                "high": prices + 1,
                "low": prices - 1,
                "close": prices,
                "volume": np.full(n, 1_000),
            }
        )

    return pa.Table.from_pandas(df)


# ──────────────────────────────────────────────────────────────
# 3.  Convenience loader for already‑downloaded parquet
# ──────────────────────────────────────────────────────────────
def load_data(symbol: str) -> pd.DataFrame:
    """
    Read the local *raw* parquet file for **symbol** (daily bars) – used by
    the trading loop.
    """
    path = DATA_DIR / f"{symbol}_1Day.parquet"
    df = pd.read_parquet(path)
    return df.set_index("timestamp").sort_index()


# ──────────────────────────────────────────────────────────────
# 4.  CLI utility  →  python -m src.download --help
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":  # pragma: no cover
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--timeframe", default="1Day")
    args = p.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    outfile = DATA_DIR / f"{args.symbol}_{args.timeframe}.parquet"

    tbl = fetch(args.symbol, args.start, args.end, args.timeframe)
    pq.write_table(tbl, outfile, compression="zstd")
    print(f"✅  Saved {tbl.num_rows} rows → {outfile}")
