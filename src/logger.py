# --- src/logger.py  (rewrite) -----------------------------------------------
"""
Logging utilities for QuantDash
================================

• CSV trade journal  ->  `log_trade(...)`
• Standard Python logger ->  `get_logger(name)` or shared `logger`
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
from pathlib import Path

# ── CSV TRADE JOURNAL ────────────────────────────────────────────────────────
LOG_PATH = Path("logs/trades.csv")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# ensure header exists once
if not LOG_PATH.exists():
    LOG_PATH.write_text(
        "ts,symbol,side,qty,limit_price,fill_price,order_id\n", encoding="utf-8"
    )


def log_trade(
    *,
    symbol: str,
    side: str,
    qty: float,
    limit_price: float | None,
    fill_price: float | None,
    order_id: str,
) -> None:
    """Append a fill (or simulated fill) to CSV."""
    with LOG_PATH.open("a", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
                dt.datetime.utcnow().isoformat(timespec="seconds"),
                symbol,
                side.upper(),
                qty,
                f"{limit_price:.4f}" if limit_price is not None else "",
                f"{fill_price:.4f}" if fill_price is not None else "",
                order_id,
            ]
        )


# ── PYTHON LOGGER HELPER ─────────────────────────────────────────────────────
def get_logger(name: str | None = None) -> logging.Logger:
    """
    Return a configured `logging.Logger`.

    Called once per module; subsequent calls with the same *name*
    return the same instance (normal logging behaviour).
    """
    log = logging.getLogger(name or "quantdash")
    if not log.handlers:  # configure only on first call
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


# shared default logger for convenience imports
logger = get_logger("quantdash")
# ---------------------------------------------------------------------------
