# ── scripts/daily_refresh.py ─────────────────────────────────────────
"""
Pull *yesterday’s* bars for every symbol listed in config.yaml
and append them to the corresponding Parquet file.

If a Parquet file does not yet exist (new symbol) it first back-fills
`BACKFILL_DAYS` of history so indicators have warm-up data.

Run manually, or schedule daily (e.g. 07:00 local time).
"""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from src.download import fetch                    # unified downloader
from src.utils import norm_sym

# ── tweak how much history to seed on first run -----------------------
BACKFILL_DAYS: int = 365
# ---------------------------------------------------------------------

# ── repo locations ----------------------------------------------------
PROJECT  = Path(__file__).resolve().parents[1]     # …/quantdash
VENV_PY  = PROJECT / ".venv" / "Scripts" / "python.exe"
CFG_FILE = PROJECT / "config.yaml"
DATA_DIR = PROJECT / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── load symbols & settings ------------------------------------------
try:
    cfg       = yaml.safe_load(CFG_FILE.read_text())
    symbols   = [norm_sym(s) for s in cfg.get("symbols", [])]
    timeframe = cfg.get("timeframe", "1Min")
except Exception as exc:
    sys.exit(f"⚠️  Could not read {CFG_FILE}: {exc}")

if not symbols:
    sys.exit("⚠️  config.yaml is missing a non-empty 'symbols:' list.")

# Date range = yesterday 00:00 UTC → NOW
yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
    "%Y-%m-%dT00:00:00Z"
)
today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ── helpers -----------------------------------------------------------
def _load_parquet_no_index(path: Path) -> pd.DataFrame:
    """
    Read an existing parquet *without* bringing back the legacy
    index column (__index_level_0__) so its schema matches fresh
    Alpaca dataframes.
    """
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path).reset_index(drop=True)


def _dl_via_cli(symbol: str, start: str, end: str) -> None:
    """
    Calls `src.cli download` in a subprocess so we re-use credential
    handling, retry logic, compression, etc.
    """
    cmd = [
        str(VENV_PY),
        "-m", "src.cli",
        "download",
        "--symbol",    symbol,
        "--start",     start,
        "--end",       end,
        "--timeframe", timeframe,
    ]
    subprocess.run(cmd, check=True, cwd=PROJECT)


# ── helper: append parquet without index-column clashes ───────────────
def _append_table(path: Path, tbl_new: pa.Table) -> None:
    """
    Append `tbl_new` to `path`, de-duplicate on 'timestamp', and make sure
    the written parquet never contains the legacy '__index_level_0__'
    column.
    """
    # --- convert NEW to pandas once ----------------------------------
    df_new = tbl_new.to_pandas().reset_index(drop=True)
    if "__index_level_0__" in df_new.columns:
        df_new = df_new.drop(columns="__index_level_0__")

    # --- load existing (if any) also as pandas without the index col ---
    if path.exists():
        df_old = pd.read_parquet(path).reset_index(drop=True)
        if "__index_level_0__" in df_old.columns:
            df_old = df_old.drop(columns="__index_level_0__")
        df_all = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_all = df_new

    # --- dedupe & sort ------------------------------------------------
    df_all = df_all.drop_duplicates("timestamp").sort_values("timestamp")

    # --- write back (index=False ensures no phantom column) -----------
    df_all.to_parquet(path, compression="zstd", index=False)



# ── download loop -----------------------------------------------------
for sym in symbols:
    pq_path = DATA_DIR / f"{sym}_{timeframe}.parquet"

    # -------- first-time back-fill -----------------------------------
    if not pq_path.exists() or pq_path.stat().st_size == 0:
        d1 = (dt.datetime.utcnow() - dt.timedelta(days=BACKFILL_DAYS)).strftime("%Y-%m-%d")
        d2 = dt.datetime.utcnow().strftime("%Y-%m-%d")
        print(f"⏳  Back-filling {sym:<7} ({BACKFILL_DAYS}-day history)…")
        try:
            _dl_via_cli(sym, d1, d2)
        except subprocess.CalledProcessError as e:
            print(f"❌  Back-fill failed for {sym}: {e}")
        continue  # back-fill already includes yesterday
    # -----------------------------------------------------------------

    # -------- daily increment (APPEND) -------------------------------
    print(f"⬇️  {sym:<7} {timeframe:>4} {yesterday} → {today}")
    try:
        df_new = fetch(sym, start=yesterday, end=today, timeframe=timeframe)

        # convert Arrow Table → DataFrame if necessary
        if isinstance(df_new, pa.Table):
            df_new = df_new.to_pandas()

        # strip any index column so schema matches existing parquet
        df_new = df_new.reset_index(drop=True)
        if "__index_level_0__" in df_new.columns:
            df_new = df_new.drop(columns="__index_level_0__")

        if df_new.empty:
            print(f"ℹ️  No new rows for {sym}")
            continue

        tbl_new = pa.Table.from_pandas(df_new)
        _append_table(pq_path, tbl_new)
        print(f"✅  Appended {len(df_new)} rows → {pq_path}")

    except Exception as err:  # noqa: BLE001
        print(f"❌  Download failed for {sym}: {err}")
# ─────────────────────────────────────────────────────────────────────
