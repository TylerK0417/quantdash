# src/plots.py
# 123
from pathlib import Path
import matplotlib.pyplot as plt

REPORTS = Path("reports")
REPORTS.mkdir(exist_ok=True)

def save_equity_curve(history, stamp: str) -> None:
    """
    history : collections.deque of cumulative equity points
    stamp   : "YYYY-MM-DD" (used in filename)
    """
    if len(history) < 3:                     # not enough data yet
        return

    plt.figure(figsize=(6, 3))
    plt.plot(history, linewidth=1.5)
    plt.title("Equity curve")
    plt.tight_layout()
    outfile = REPORTS / f"equity_{stamp}.png"
    plt.savefig(outfile, dpi=120, bbox_inches="tight")
    plt.close()

