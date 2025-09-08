# ── src/telemetry.py ──────────────────────────────────────────────────
"""
Rich dashboard helper for the paper-trading loop.

Call  ▸ dash = init_dash()
then ▸ dash.update(stats_dict, positions_dict)  every cycle.
"""

from __future__ import annotations

import statistics
from collections import deque
from typing import Any, Deque, Dict
import pandas as pd

from rich.align import Align
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


__all__ = ["init_dash", "LiveDashboard", "Dashboard", "shutdown"]

# ───────────────────────────────────────────────────────────────────────
console: Console = Console()
_live: Live | None = None                       # singleton Live context
HISTORY_LEN: int = 120                          # show last n equity pts
# ───────────────────────────────────────────────────────────────────────


# helper ───────────────────────────────────────────────────────────────
def _stats_panel(stats: Dict[str, float]) -> Panel:
    rows = Table.grid()
    rows.add_column(justify="right")
    rows.add_column(justify="left")

    rows.add_row("Gross:", f"${stats['gross'] :,.0f}")
    rows.add_row("U-PnL:", f"{stats['u_pnl'] :+,.0f}")
    rows.add_row("R-PnL:", f"{stats['realised_pnl']:+,.0f}")
    rows.add_row("Risk@Stop:", f"${stats['risk'] :,.0f}")

    return Panel(rows, title="Telemetry", border_style="green")


# ------------------------------------------------------------------ #
def _pos_table(positions: Dict[str, Dict[str, Any]] | pd.DataFrame) -> Panel:
    """
    Build the “Open Positions” Rich table.

    • Accepts either a dict-of-dicts or a pandas.DataFrame.
    • Keeps rows that LOOK like instruments (AAPL, BTCUSD, ETH-USD, …)
      and that have both “quantity” and “avg_entry”.
    • Quantity ≤ 0 rows are filtered out, but fractional crypto lots
      such as 0.002 BTC are allowed.
    """
    # --- normalise to DataFrame ------------------------------------
    if isinstance(positions, pd.DataFrame):
        df_pos = positions.copy()
    else:                                     # dict-of-dicts
        df_pos = pd.DataFrame(positions).T

    # plausible symbols: 1-10 uppercase letters, dots, slashes or dashes
    mask_sym = df_pos.index.str.match(r"^[A-Z./\-]{1,10}$")
    mask_qty = (df_pos.get("quantity", 0).fillna(0) > 0)
    mask_has = df_pos.columns.isin(["avg_entry"])
    mask_has = df_pos["avg_entry"].notna() if mask_has.any() else False

    df_pos = df_pos[mask_sym & mask_qty & mask_has]

    # --- build Rich table ------------------------------------------
    tbl = Table(
        title="Open Positions",
        show_header=True,
        header_style="bold",
        show_edge=True,
        expand=True,
    )
    tbl.add_column("Symbol", style="cyan bold")
    tbl.add_column("Qty",    justify="right")
    tbl.add_column("Entry",  justify="right")
    tbl.add_column("Stop",   justify="right")
    tbl.add_column("TP",     justify="right")

    for sym, row in df_pos.iterrows():
        qty = row["quantity"]
        # cryptos / fractional lots: show up to 8 dp; equities: 0 dp
        qty_fmt = (
            f"{qty:,.8f}".rstrip("0").rstrip(".")
            if (qty < 1 or "/" in sym or "-" in sym)
            else f"{qty:,.0f}"
        )
        tbl.add_row(
            sym,
            qty_fmt,
            f"{row['avg_entry']:.2f}",
            "-" if pd.isna(row.get("stop")) else f"{row['stop']:.2f}",
            "-" if pd.isna(row.get("tp"))   else f"{row['tp']  :.2f}",
        )

    if len(tbl.rows) == 0:                          # no valid positions
        tbl.add_row("—", "—", "—", "—", "—")

    return Panel(tbl, border_style="cyan")

def _spark(history: Deque[float]) -> RenderableType:
    if len(history) < 2:
        return Align.center(Text("No data yet…", style="dim"), vertical="middle")

    lo, hi = min(history), max(history)
    span = hi - lo or 1
    chars = "▁▂▃▄▅▆▇█"
    spark = "".join(chars[int((v - lo) / span * (len(chars) - 1))] for v in history)
    return Align.center(Text(spark, style="magenta"), vertical="middle")
# ───────────────────────────────────────────────────────────────────────


class Dashboard:
    """Core dashboard – exposed as both `Dashboard` and `LiveDashboard`."""

    def __init__(self, max_hist: int = HISTORY_LEN) -> None:
        self.history: Deque[float] = deque(maxlen=max_hist)
        self.telemetry: Panel = Panel("")
        self.positions: Panel = Panel("")
        self.spark: RenderableType = Text("")

    def update(
        self,
        stats: Dict[str, float],
        positions: Dict[str, Dict[str, Any]],
    ) -> None:
        # add equity point BEFORE computing spark so latest point shows up
        self.history.append(stats["u_pnl"] + stats["realised_pnl"])

        self.telemetry = _stats_panel(stats)
        self.positions = _pos_table(positions)
        self.spark = _spark(self.history)

        if _live is not None:
            _live.update(self.layout())

    # ------------------------------------------------------------------
    def layout(self) -> Group:
        return Group(
            self.telemetry,
            self.positions,
            Panel(self.spark, title="Equity curve", border_style="cyan"),
        )


# back-compat alias
LiveDashboard = Dashboard


# public helpers ───────────────────────────────────────────────────────
def init_dash() -> Dashboard:
    """Create (or retrieve) the on-screen Rich dashboard."""
    global _live
    dash = Dashboard()
    if _live is None:
        _live = Live(dash.layout(), console=console, refresh_per_second=4)
        _live.start()
    return dash


def shutdown() -> None:
    """Stop Rich Live so the terminal is restored nicely."""
    global _live
    if _live is not None:
        _live.stop()
        _live = None
# ----------------------------------------------------------------------
