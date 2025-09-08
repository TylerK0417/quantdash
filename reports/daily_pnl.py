# reports/daily_pnl.py
"""
Run once per day (cron or Task Scheduler) to record and print account equity.
"""
from __future__ import annotations
import datetime as dt
from alpaca.trading.client import TradingClient
from dotenv import load_dotenv
from src.storage import append_equity

load_dotenv()
cli = TradingClient(paper=True)        # uses keys in .env

def main():
    today = dt.datetime.utcnow().date()
    yday  = today - dt.timedelta(days=1)
    equity = float(cli.get_account().equity)
    append_equity(equity, yday)
    print(f"📈  {yday}: equity = ${equity:,.2f}")

if __name__ == "__main__":
    main()
