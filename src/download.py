"""
download.py | Historical OHLCV fetcher for QuantDash

Usage:
    python -m src.download --symbol SPY --start 2024-01-01 --end 2024-01-31 --timeframe 1Day
"""

import argparse, os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.timeframe import TimeFrame
from alpaca.data.requests import StockBarsRequest
import pyarrow.parquet as pq
import pyarrow as pa

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def tf(code: str) -> TimeFrame:
    mapping = {
        "1Day": TimeFrame.Day,
        "1Hour": TimeFrame.Hour,
        "15Min": TimeFrame.Minute,
    }
    return mapping[code]


def fetch(symbol: str, start: str, end: str, timeframe: str) -> pa.Table:
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


def main():
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


if __name__ == "__main__":
    main()
