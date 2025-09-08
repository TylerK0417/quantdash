# ── download.py  |  Historical OHLCV fetcher for QuantDash ────────────────
"""
Download OHLCV bars from Alpaca and store them as compressed Parquet files.

• Equities → StockHistoricalDataClient (IEX feed)
• Crypto   → CryptoHistoricalDataClient (BTCUSD, ETHUSDT …)

Called by `qdash dl_batch` and `scripts/daily_refresh.py`.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from src.utils import norm_sym

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from alpaca.data.enums import DataFeed
from alpaca.data.historical import (
    StockHistoricalDataClient,
    CryptoHistoricalDataClient,
)
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from dotenv import load_dotenv

# ── paths & constants -------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CRYPTO_SUFFIXES = ("USD", "USDT")  # simple heuristic: BTCUSD, DOGEUSDT …

# ── helper: map timeframe code ➜ Alpaca enum -------------------------------
def tf(code: str) -> TimeFrame:
    mapping = {
        "1Min":  TimeFrame.Minute,
        "15Min": getattr(TimeFrame, "Minute15", TimeFrame.Minute),
        "1Hour": TimeFrame.Hour,
        "1Day":  TimeFrame.Day,
    }
    return mapping[code]


def _is_crypto(symbol: str) -> bool:
    """Very naive check: ends with USD/USDT."""
    return symbol.upper().endswith(CRYPTO_SUFFIXES)

# ── core fetcher ------------------------------------------------------------
def fetch(symbol: str, start: str, end: str, timeframe: str) -> pa.Table:
    """
    Fetch OHLCV bars for `symbol` between ISO dates *start* and *end*
    at granularity *timeframe*. Returns a pyarrow.Table.
    """
    load_dotenv()  # ensure env vars loaded (used by scheduler)

    start_dt = datetime.fromisoformat(start)
    end_dt   = datetime.fromisoformat(end)
    tframe   = tf(timeframe)

    if _is_crypto(symbol):
        # -------- crypto pathway -----------------------------------
        client = CryptoHistoricalDataClient(
            os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_API_SECRET")
        )

        # Alpaca crypto-history expects a slash pair (BTCUSD → BTC/USD)
        sym_api = f"{symbol[:3]}/{symbol[3:]}" if "/" not in symbol else symbol

        req = CryptoBarsRequest(
            symbol_or_symbols=sym_api,
            timeframe=tframe,
            start=start_dt,
            end=end_dt,
        )
        bars_df = client.get_crypto_bars(req).df.reset_index()

    else:
        # -------- equities pathway ---------------------------------
        client = StockHistoricalDataClient(
            api_key=os.getenv("ALPACA_API_KEY"),
            secret_key=os.getenv("ALPACA_API_SECRET"),
        )
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tframe,
            start=start_dt,
            end=end_dt,
            feed=DataFeed.IEX,
        )
        bars_df = client.get_stock_bars(req).df.reset_index()

    # unify schema --------------------------------------------------
    bars_df.rename(columns={"t": "timestamp"}, inplace=True, errors="ignore")
    return pa.Table.from_pandas(bars_df)


# ── helper to load Parquet back into pandas -------------------------------
def load_data(symbol: str, timeframe: str = "1Day") -> pd.DataFrame:
    """
    Return a DataFrame of OHLCV bars for *symbol*/*timeframe*.

    • Accepts either “BTC/USD” (slash form) or “BTC_USD” (safe-file form).
    • Looks for data/raw/<SAFE_SYMBOL>_<TF>.parquet.
    • Sets 'timestamp' as index (ascending).
    """
            
    path = DATA_DIR / f"{norm_sym(symbol)}_{timeframe}.parquet"

    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_parquet(path)
    if "timestamp" in df.columns:              # keep back-compat
        df = df.set_index("timestamp")

    return df.sort_index()

# ── CLI entry-point ---------------------------------------------------------
def main(cli_args: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Download Alpaca OHLCV to Parquet.")
    p.add_argument("--symbol",   required=True, help="Ticker e.g. SPY or BTCUSD")
    p.add_argument("--start",    required=True, help="YYYY-MM-DD (inclusive)")
    p.add_argument("--end",      required=True, help="YYYY-MM-DD (exclusive)")
    p.add_argument(
        "--timeframe",
        default="1Day",
        choices=["1Min", "15Min", "1Hour", "1Day"],
    )
    ns = p.parse_args(cli_args)

    
   
    outfile = DATA_DIR / f"{norm_sym(ns.symbol)}_{ns.timeframe}.parquet"

    tbl = fetch(ns.symbol.upper(), ns.start, ns.end, ns.timeframe)
    pq.write_table(tbl, outfile, compression="zstd")
    print(f"✅  Saved {tbl.num_rows:,} rows → {outfile}")


if __name__ == "__main__":
    main()
