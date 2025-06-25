"""
download.py | Historical OHLCV fetcher for QuantDash

Usage
-----
python -m src.download \
    --symbol SPY --start 2024-01-01 --end 2024-01-31 --timeframe 1Day
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from dotenv import load_dotenv

# ──────────────────────────────────────────────────────────────────────────────
# Globals
# ──────────────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def tf(code: str) -> TimeFrame:
    """Return the Alpaca ``TimeFrame`` enum for *code* (e.g. ``"1Day"``)."""
    mapping = {
        "1Day": TimeFrame.Day,
        "1Hour": TimeFrame.Hour,
        "15Min": TimeFrame.Minute,
    }
    try:
        return mapping[code]
    except KeyError as exc:  # pragma: no cover
        raise ValueError(f"Unsupported timeframe: {code!r}") from exc


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────
def fetch(symbol: str, start: str, end: str, timeframe: str = "1Day") -> pa.Table:
    """
    Download bars from Alpaca and return a **PyArrow Table**.

    Parameters
    ----------
    symbol:
        Ticker (e.g. ``"SPY"``).
    start, end:
        ISO-8601 date strings, inclusive.
    timeframe:
        One of ``"1Day" | "1Hour" | "15Min"``.
    """
    load_dotenv()

    client = StockHistoricalDataClient(
        api_key=os.getenv("ALPACA_API_KEY"),
        secret_key=os.getenv("ALPACA_API_SECRET"),
    )

    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=tf(timeframe),
        start=datetime.fromisoformat(start),
        end=datetime.fromisoformat(end),
    )

    df = client.get_stock_bars(req).df.reset_index()
    return pa.Table.from_pandas(df)


def load_data(symbol: str) -> pd.DataFrame:
    """
    Return the cached daily Parquet for *symbol* as a DataFrame,
    indexed and sorted by ``timestamp``.
    """
    path = DATA_DIR / f"{symbol}_1Day.parquet"
    df = pd.read_parquet(path)
    return df.set_index("timestamp").sort_index()


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--timeframe", default="1Day")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    outfile = DATA_DIR / f"{args.symbol}_{args.timeframe}.parquet"

    tbl = fetch(args.symbol, args.start, args.end, args.timeframe)
    pq.write_table(tbl, outfile, compression="zstd")
    print(f"✅  Saved {tbl.num_rows} rows → {outfile}")


if __name__ == "__main__":
    main()
