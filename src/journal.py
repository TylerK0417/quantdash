# ── src/journal.py ─────────────────────────────────────────────
from __future__ import annotations
import csv, datetime as dt
from pathlib import Path
from typing import Dict, Any

JOURNAL = Path("data/trades.csv")
JOURNAL.parent.mkdir(exist_ok=True)

_HDR = [
    "timestamp",
    "gross",
    "u_pnl",
    "realised_pnl",
    "risk",
]

def _write(row: Dict[str, Any]) -> None:
    first = not JOURNAL.exists()
    with JOURNAL.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if first:
            w.writeheader()
        w.writerow(row)

# public helpers ------------------------------------------------
def log_fill(**row: Any) -> None:
    """
    Call from Trader after every *executed* order.
    Expected keys:
      timestamp, symbol, side, qty, limit_price, fill_price, order_id
    """
    row.setdefault("timestamp",
                   dt.datetime.utcnow().isoformat(timespec="seconds"))
    _write(row)

def log_equity(**stats: Dict[str, Any]) -> None:
    """
    Append a one-row equity snapshot to data/equity_log.csv.

    Expected keys in **stats:
        gross, u_pnl, realised_pnl, risk   (all floats)
    """
    row = {
        "timestamp": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "gross":        round(stats.get("gross", 0.0), 2),
        "u_pnl":        round(stats.get("u_pnl", 0.0), 2),
        "realised_pnl": round(stats.get("realised_pnl", 0.0), 2),
        "risk":         round(stats.get("risk", 0.0), 2),
    }

    write_header = not JOURNAL.exists()
    with JOURNAL.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_HDR)
        if write_header:
            w.writeheader()
        w.writerow(row)
