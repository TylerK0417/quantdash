# src/dashboard.py
from datetime import datetime
from rich.console import Console
from rich.live import Live
from rich.table import Table

class Dashboard:
    """
    Dumb-simple TUI refreshed each trading cycle.
    Call .update(stats, positions) – that’s it.
    """

    def __init__(self) -> None:
        self.console = Console()
        self.live = Live(auto_refresh=False, console=self.console)
        self.live.__enter__()            # keep context open

    # ------------------------------------------------------------------
    def _build_panel(self, stats: dict, positions: dict) -> Table:
        """Return a Rich Table that holds both summary + open positions."""
        outer = Table.grid(padding=(1, 2))
        # --- headline --------------------------------------------------
        head = Table(title=f" QuantDash  {datetime.now():%H:%M:%S} ")
        head.add_column("Metric")
        head.add_column("Value", justify="right")
        for k in ("gross", "u_pnl", "realised_pnl", "risk"):
            head.add_row(k, f"{stats.get(k, 0):,.0f}")
        outer.add_row(head)

        # --- open positions -------------------------------------------
        if positions:
            pos = Table(title=" Open Positions ")
            pos.add_column("Sym")
            pos.add_column("Qty", justify="right")
            pos.add_column("Last", justify="right")
            pos.add_column("Stop", justify="right")
            pos.add_column("U-PnL", justify="right")
            for sym, p in positions.items():
                pos.add_row(
                    sym,
                    f"{p['quantity']:.0f}",
                    f"{p.get('last', 0):.2f}",
                    f"{p.get('stop', '')}",
                    f"{p.get('u_pnl', 0):+,.0f}",
                )
            outer.add_row(pos)
        return outer

    # ------------------------------------------------------------------
    def update(self, stats: dict, positions: dict) -> None:
        """Hot-swap the display."""
        self.live.update(self._build_panel(stats, positions), refresh=True)

    # ------------------------------------------------------------------
    def __del__(self) -> None:
        try:
            self.live.__exit__(None, None, None)
        except Exception:
            pass
