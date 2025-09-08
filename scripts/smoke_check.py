# ── scripts/smoke_check.py ─────────────────────────────────────────────
"""
Run:  python scripts/smoke_check.py

Exits 0 when everything looks sane, non-zero otherwise.
Keeps network/API calls to a minimum (Alpaca only if keys set).
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml
import pandas as pd

# ---- project imports --------------------------------------------------
from src.trader import Trader
from src.signals import compute_signals
from src.utils import norm_sym, is_crypto

GREEN = "\x1b[32m"
RED   = "\x1b[31m"
RESET = "\x1b[0m"

cfg_path = Path(__file__).resolve().parent.parent / "config.yaml"
cfg = yaml.safe_load(cfg_path.read_text())

def ok(msg: str) -> None:
    print(f"{GREEN}✅ {msg}{RESET}")

def fail(msg: str) -> None:
    print(f"{RED}❌ {msg}{RESET}")
    sys.exit(1)

# 1 ─── YAML keys present ───────────────────────────────────────────────
required_keys = ["symbols", "timeframe", "short", "long", "risk_pct", "trail_pct"]
missing = [k for k in required_keys if k not in cfg]
if missing:
    fail(f"Missing keys in config.yaml: {missing}")
ok("config.yaml parsed and has required keys")

# 2 ─── Parquet freshness (≤ 10 min) ────────────────────────────────────
now_utc = datetime.now(timezone.utc)
stale = []
for sym in cfg["symbols"]:
    sym_norm = norm_sym(sym)
    path = Path("data/raw") / f"{sym_norm}_{cfg['timeframe']}.parquet"
    if not path.exists():
        stale.append(sym_norm + " (file missing)")
        continue
    last_ts = pd.read_parquet(path, columns=["timestamp"]).timestamp.iloc[-1]
    age = now_utc - last_ts.to_pydatetime()
    if age > timedelta(minutes=10):
        stale.append(f"{sym_norm} ({age.total_seconds()/60:.1f} min old)")
if stale:
    fail(f"Stale or missing data: {stale}")
ok("Parquet data fresh for all symbols")

# 3 ─── MA-crossover not all flat ───────────────────────────────────────
active_sigs = 0
for sym in cfg["symbols"]:
    sym_norm = norm_sym(sym)
    path = Path("data/raw") / f"{sym_norm}_{cfg['timeframe']}.parquet"
    df = pd.read_parquet(path).tail(cfg["long"] + 2)

    sig_series = compute_signals(df, cfg["short"], cfg["long"])  # Series of ints
    latest_bar = sig_series.iloc[-1]                              # latest values

    if (latest_bar != 0).any():          # any component +1 / -1?
        active_sigs += 1

if active_sigs == 0:
    fail("Signal engine returned 0 for every symbol (unlikely but check MAs)")
ok(f"Signal sanity: {active_sigs} non-zero signals right now")

# 4 ─── Sizing saner than zero ─────────────────────────────────────────
sample_sym = norm_sym(cfg["symbols"][0])
path = Path("data/raw") / f"{sample_sym}_{cfg['timeframe']}.parquet"
df = pd.read_parquet(path).tail(cfg["long"] + 2)
trader = Trader(
    paper=True,
    risk_pct = cfg["risk_pct"],
    trail_pct= cfg["trail_pct"],
)
qty = trader._calc_qty(df, df.close.iloc[-1])
if qty < 1:
    fail(f"Position sizing returned {qty} for {sample_sym}; risk_pct too low?")
ok(f"Sizing check: {sample_sym} size={qty} shares")

# 5 ─── Trader round-trip open/close (paper) ───────────────────────────
sym_norm = sample_sym

# ensure we start flat
trader.portfolio.positions.pop(sym_norm, None)

# monkey-patch submit so no real API call fires
trader._submit = lambda *a, **kw: None

# build a one-row DataFrame the method expects
bar_df = df.tail(1).copy()

# ---- create a guaranteed non-NaN signal -----------------------------
open_sig  = pd.Series([+1], index=bar_df.index)   # force +1  (enter)
close_sig = pd.Series([-1], index=bar_df.index)   # force -1  (exit)
bar_df["position"] = open_sig                     # will be overwritten later
# --------------------------------------------------------------------

# open trade
trader.execute_signals(sym_norm, bar_df)

# overwrite with close signal and exit
bar_df["position"] = close_sig
trader.execute_signals(sym_norm, bar_df)

if sym_norm in trader.portfolio.positions:
    fail("Trader failed round-trip open/close in paper mode")
ok("Trader round-trip open/close successful")
