"""
download.py | Historical OHLCV fetcher for QuantDash

Usage:
    python -m src.download --symbol SPY --start 2024-01-01 --end 2024-01-31 --timeframe 1Day
"""

import argparse
import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

import pyarrow.parquet as pq
import pyarrow as pa


def fetch(symbol: str, start: datetime, end: datetime, timeframe: str, outdir: str):
    """
    Fetch OHLCV bars for `symbol` from Alpaca between `start` and `end`
    at resolution `timeframe`, then write to a parquet file under `outdir`.
    """
    load_dotenv()  # loads ALPACA_API_KEY / ALPACA_API_SECRET from .env

    client = StockHistoricalDataClient(
        api_key=os.getenv("ALPACA_API_KEY"),
        secret_key=os.getenv("ALPACA_API_SECRET"),
    )

    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        start=start,
        end=end,
        timeframe=TimeFrame[timeframe],
    )
    bars = client.get_stock_bars(req).df  # pandas DataFrame

    table = pa.Table.from_pandas(bars)
    filename = (
        Path(outdir)
        / f"{symbol}-{timeframe}-{start:%Y%m%d}-{end:%Y%m%d}.parquet"
    )
    pq.write_table(table, filename)

    print(f"Saved {len(bars)} bars to {filename}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="quantdash-download",
        description="Fetch OHLCV from Alpaca and save as Parquet."
    )
    p.add_argument(
        "--symbol",
        required=True,
        help="Ticker symbol (e.g. AAPL)",
    )
    p.add_argument(
        "--start",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        required=True,
        help="Start date YYYY-MM-DD",
    )
    p.add_argument(
        "--end",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        required=True,
        help="End date YYYY-MM-DD",
    )
    p.add_argument(
        "--timeframe",
        default="1D",
        choices=[tf.name for tf in TimeFrame],
        help="Data resolution (e.g. 1Min, 5Min, 1H, 1D)",
    )
    p.add_argument(
        "--outdir",
        default=".",
        help="Directory to save output Parquet files",
    )
    return p.parse_args()


def main():
    args = parse_args()
    fetch(
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        timeframe=args.timeframe,
        outdir=args.outdir,
    )


if __name__ == "__main__":
    main()
