# src/storage.py
"""
Tiny persistence helpers for QuantDash.
All state is kept under   data/state/   (auto-created).
"""
from __future__ import annotations
import json, pathlib, datetime as dt, pandas as pd

DATA_DIR = pathlib.Path("data/state")
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── portfolio (positions / stops) ────────────────────────────────────
_PORT_JSON = DATA_DIR / "portfolio.json"

def save_portfolio(positions: dict) -> None:
    _PORT_JSON.write_text(json.dumps(positions, indent=2))


def load_portfolio() -> dict[str, dict]:
    if _PORT_JSON.exists():
        return json.loads(_PORT_JSON.read_text())
    return {}


# ── trade blotter  (append-only CSV) ─────────────────────────────────
_BLOTTER = DATA_DIR / "trades.csv"

def append_trade(row: dict) -> None:
    """row must contain at least timestamp, symbol, side, qty, price."""
    df = pd.DataFrame([row])
    write_header = not _BLOTTER.exists()
    df.to_csv(_BLOTTER, mode="a", header=write_header, index=False)


# ── equity curve CSV helper (used by daily_pnl.py) ───────────────────
_EQUITY = DATA_DIR / "equity_curve.csv"

def append_equity(equity: float, as_of: dt.date) -> None:
    pd.DataFrame([{"date": str(as_of), "equity": equity}]).to_csv(
        _EQUITY, mode="a", header=not _EQUITY.exists(), index=False
    )
