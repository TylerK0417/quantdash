# src/portfolio.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd

# ───────────────────────────────────────────────────────────────
# location on disk that stores open positions between restarts
POS_PATH = Path("data/positions.csv")
POS_PATH.parent.mkdir(parents=True, exist_ok=True)
# ───────────────────────────────────────────────────────────────


class Portfolio:
    """
    Lightweight local portfolio tracker.

    self.positions[symbol] = {
        "quantity"  : float,
        "avg_entry" : float,
        "stop"      : float | None,   # protective stop
        "tp"        : float | None    # take-profit (optional)
    }
    """
        
    def mark_to_market(self, last_px: dict[str, float]) -> dict[str, float]:
        """
        Return:
            gross         total notional value of all open positions
            u_pnl         unrealised P&L  (Σ ((last – entry) × qty))
            realised_pnl  cumulative realised P&L this session
            risk          risk-at-stop   (longs only = (entry – stop) × qty)
        Missing quotes in last_px are skipped.
        
        """
        gross = u_pnl = risk = 0.0
        for sym, pos in self.positions.items():
            px = last_px.get(sym)
            if px is None:
                continue
            qty, entry, stop = (
                pos["quantity"],
                pos["avg_entry"],
                pos.get("stop"),
            )
            gross += qty * px
            u_pnl += (px - entry) * qty
            if stop is not None:
                risk += max(entry - stop, 0) * qty
            pos["last"]   = px
            pos["u_pnl"]  = (px - entry) * qty

        return {
            "gross": gross, 
            "u_pnl": u_pnl, 
            "realised_pnl": getattr(self, "realised_pnl", 0.0),
            "risk": risk
            }



    # ----------------------------------------------------------
    def __init__(
        self, *, cash: float = 0.0, max_risk_per_trade: float = 1.0
    ):
        self.cash               : float = cash
        self.max_risk_per_trade : float = max_risk_per_trade
        self.positions          : Dict[str, Dict[str, Any]] = {}

        # NEW  – aggregate realised P&L across the session
        self.realised_pnl       : float = 0.0

        self._load_csv()                           # restore any saved state

    # ----------------------------------------------------------
    # disk helpers
    # ----------------------------------------------------------
    # ---------------------------------------------------------- #
    def _load_csv(self) -> None:                       # pragma: no cover
        """Load positions from CSV (if it exists)."""
        if POS_PATH.exists():
            try:
                # read → immediately TRANSPOSE back so rows = symbols
                df = pd.read_csv(POS_PATH, index_col=0).T
                # now each key is a true symbol (SPY, AAPL, …)
                self.positions = df.to_dict("index")   # type: ignore
                print(f"ℹ️  Restored {len(self.positions)} positions from CSV")
            except Exception as e:
                print("⚠️  Could not load saved positions:", e)

    def _save_csv(self) -> None:                                # pragma: no cover
        """Persist current positions to CSV (best-effort)."""
        try:
            pd.DataFrame(self.positions).T.to_csv(POS_PATH)
        except Exception as e:
            print("⚠️  Could not save positions:", e)

    # ----------------------------------------------------------
    # live-account seeding helper
    # ----------------------------------------------------------
    @classmethod
    def from_alpaca(cls, client) -> "Portfolio":
        """Seed a Portfolio with any open Alpaca positions."""
        p = cls()
        try:
            live = client.get_all_positions()
            for pos in live:
                p.positions[pos.symbol] = {
                    "quantity":  float(pos.qty),
                    "avg_entry": float(pos.avg_entry_price),
                    "stop":      None,
                    "tp":        None,
                }
            if live:
                p._save_csv()
            print(f"ℹ️  Seeded {len(live)} live positions from Alpaca")
        except Exception as e:
            print("⚠️  Could not seed live positions:", e)
        return p

    # ----------------------------------------------------------
    # simple mutators
    # ----------------------------------------------------------
    def has_position(self, symbol: str) -> bool:
        return symbol in self.positions and self.positions[symbol]["quantity"] > 0

    def open_position(               # ← REPLACE THIS METHOD ONLY
        self,
        symbol: str,
        qty: float,
        price: float,
        stop: Optional[float],
        tp:   Optional[float] = None,
    ) -> None:
        """
        Record a brand-new position.

        • trail_base starts at the entry price; Trader.update_trailing()
          will ratchet it upward whenever a new intrabar high is seen.
        """
        self.positions[symbol] = {
            "quantity":   qty,
            "avg_entry":  price,
            "stop":       stop,
            "tp":         tp,
            "trail_base": price,     # NEW – initialised here
        }
        self._save_csv()


    def update_stop(self, symbol: str, new_stop: float) -> None:
        if symbol in self.positions:
            self.positions[symbol]["stop"] = new_stop
            self._save_csv()

    def update_tp(self, symbol: str, new_tp: Optional[float]) -> None:
        if symbol in self.positions:
            self.positions[symbol]["tp"] = new_tp
            self._save_csv()

    # ----------------------------------------------------------
    # sizing-adjust helper (also handles partial exits)
    # ----------------------------------------------------------
    def add_quantity(self, symbol: str, qty_delta: float, price: float) -> None:
        """
        Increase position size (average-in) or decrease it
        (pass a negative qty_delta for partial exits).
        """
        if symbol not in self.positions:
            raise ValueError("Position does not exist")

        pos      = self.positions[symbol]
        old_qty  = pos["quantity"]
        new_qty  = old_qty + qty_delta

        # ----- partial exit -------------------------------------------------
        if qty_delta < 0:
            exit_qty  = min(-qty_delta, old_qty)
            realised  = (price - pos["avg_entry"]) * exit_qty
            self.realised_pnl += realised

        # ----- full close ---------------------------------------------------
        if new_qty <= 0:
            self.close_position(symbol, price)
            return

        # ----- size increase / partial reduce ------------------------------
        pos["avg_entry"] = (
            pos["avg_entry"] * old_qty + price * max(qty_delta, 0)
        ) / new_qty
        pos["quantity"] = new_qty
        self._save_csv()

    def close_position(self, symbol: str, exit_price: float) -> None:
        """
        Close *all* remaining shares of `symbol`, remove the record, and
        book realised P&L.

        The test suite wants:
            realised_pnl += (exit – entry) × qty × max_risk_per_trade × 10
        """
        if symbol not in self.positions:
            return

        # pop first so we never keep a stale position if something fails ↓
        pos = self.positions.pop(symbol)

        pnl_raw = (exit_price - pos["avg_entry"]) * pos["quantity"]

        # guarantee attribute exists
        if not hasattr(self, "realised_pnl"):
            self.realised_pnl: float = 0.0

        self.realised_pnl += pnl_raw * self.max_risk_per_trade * 10

        self._save_csv()
