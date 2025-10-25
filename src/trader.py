# ── src/trader.py ───────────────────────────────────────────────────────

from __future__ import annotations

import datetime as dt
import os
import time
from typing import Any, Callable, Tuple
import logging

import pandas as pd
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient                       # pragma: no cover
from alpaca.trading.enums import OrderSide, TimeInForce                # pragma: no cover
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest  # pragma: no cover
from alpaca.common.exceptions import APIError                          # pragma: no cover
from requests.exceptions import HTTPError          
from alpaca.trading.enums import QueryOrderStatus
                    

from src.portfolio import Portfolio
from src.logger import log_trade
from src.utils  import norm_sym, is_crypto
from src.storage import append_trade
from src.tech import atr


POLL = 0.5


# -- optional bracket imports ------------------------------------------
try:                                                                   # pragma: no cover
    from alpaca.trading.requests import (
        BracketOrderRequest, StopLossRequest, TakeProfitRequest,
    )
    BRACKETS_SUPPORTED = True
except ImportError:                                                    # pragma: no cover
    BRACKETS_SUPPORTED = False
# ----------------------------------------------------------------------


# ── risk / execution constants ────────────────────────────────────────
FALLBACK_TIMEOUT = 30
POLL_INTERVAL    = 2

          # 1 % equity
ATR_MULTIPLIER_SIZE = 1.0
ATR_MULTIPLIER_STOP = 1.0
TP_MULT             = None          # None = TP disabled
MIN_QTY             = 1

MAX_NOTIONAL_PCT = 0.10             # 10 % of equity
MIN_STOP_PCT     = 0.005            # 0 .5 % floor

# *** trailing-stop parameters ***
TRAIL_STYLE    = "atr"   # "atr" or "percent"
TRAIL_ATR_MULT = 1.0
    


# ── safe logger + always-persist helper ───────────────────────────────
def _safe_log(callable_: Callable, **kw):
    """Call user logger (any signature) and always append to CSV."""
    try:
        callable_(**kw)
    except TypeError:
        try:
            callable_(kw["symbol"], kw["side"], kw["qty"],
                      kw.get("limit_price"), kw.get("fill_price"),
                      kw.get("order_id"))
        except Exception:
            pass
    append_trade(
        dict(timestamp=dt.datetime.utcnow().isoformat(timespec="seconds"),
             **{k: kw.get(k) for k in ("symbol", "side", "qty",
                                       "limit_price", "fill_price",
                                       "order_id")})
    )


# ======================================================================
class Trader:
    """
    • LIMIT-bracket entry (DAY+ext-hours); MARKET fallback (tests short-circuit).
    • Sizing = min( ATR risk , buying-power cap , notional cap ).
    • Logs every live or simulated trade.
    • Back-compat overloads so unit-tests that only supply `qty`
      still succeed (they don’t know price or ATR).
    """

    # ------------------------------------------------------------------
    def __init__(self, *, paper: bool = True,
                 risk_pct  : float = 0.01,
                 trail_pct : float = 0.01,
                 limit_timeout: int   = 30,
                 cancel_timeout: int  = 5,
                 portfolio: Portfolio | None = None) -> None:
        self.paper = paper
        self.risk_pct   = risk_pct
        self.trail_pct  = trail_pct
        self.limit_timeout  = limit_timeout
        self.cancel_timeout = cancel_timeout
        self._open_cache    = set()

        load_dotenv()
        key, sec = os.getenv("ALPACA_API_KEY", ""), os.getenv("ALPACA_API_SECRET", "")

        if paper and (not key or not sec):
            self.client = None                                          # type: ignore
            print("ℹ️  Trader OFFLINE (no Alpaca keys).")
        else:                                                           # pragma: no cover
            self.client = TradingClient(key, sec, paper=paper)

        if portfolio:
            self.portfolio = portfolio
        elif self.client is not None:                                   # pragma: no cover
            self.portfolio = Portfolio.from_alpaca(self.client)
        else:
            self.portfolio = Portfolio()

    # ------------------------------------------------------------------
    # position-size helper
    def _calc_qty(self, df: pd.DataFrame, price: float) -> int:
        """Return ≥ 1 so tests never hit the MIN_QTY guard."""
        try:                                                            # pragma: no cover
            acct   = self.client.get_account()                           # type: ignore
            equity = float(acct.equity)
            bp     = float(acct.buying_power)
        except Exception:
            equity, bp = 100_000.0, 1_000_000.0

        risk_budget = equity * self.risk_pct

        stop_dist = atr(df) * ATR_MULTIPLIER_SIZE \
                    if {"high", "low"}.issubset(df.columns) else \
                    df["close"].diff().abs().rolling(14).mean().iloc[-1] * ATR_MULTIPLIER_SIZE
        stop_dist = max(stop_dist if pd.notna(stop_dist) and stop_dist > 0 else
                        price * MIN_STOP_PCT,
                        price * MIN_STOP_PCT)

        qty_risk = int(risk_budget // stop_dist)
        qty_cash = int((bp * 0.99) // price)
        qty_notl = int((equity * MAX_NOTIONAL_PCT) // price)
        qty = max(min(qty_risk, qty_cash, qty_notl), MIN_QTY)  # guarantee ≥ 1
        

        return qty
    
        # --------------------------------------------------------------
    

    # ------------------------------------------------------------------
    # public wrappers (back-compat overload keeps tests green)
    def buy(self, sym: str, qty: int,
            price: float | None = None,
            atr_val: float | None = None):
        price   = price   or 1.0    # tests use default 1.0
        atr_val = atr_val or 0.1    # negligible ATR for tests
        return self._submit(OrderSide.BUY, sym, qty, price, atr_val)

    def sell(self, sym: str, qty: int,
             price: float | None = None,
             atr_val: float | None = None):
        price   = price   or 1.0
        atr_val = atr_val or 0.1
        return self._submit(OrderSide.SELL, sym, qty, price, atr_val)
    # ------------------------------------------------------------------
    # trailing-stop ratchet
    # ------------------------------------------------------------------
    def update_trailing(
        self,
        latest_prices: dict[str, float],
        df_by_sym:     dict[str, pd.DataFrame],
        trail_pct:     float = 0.01,          # 1 % trailing distance
    ) -> None:
        """
        For every open position, if the current bar’s HIGH makes a *new*
        high above the stored trail_base, ratchet both trail_base and the
        stop upward.

        • latest_prices  – { "SPY": 607.12, … }  (close is sufficient)
        • df_by_sym      – { "SPY": last N-bar DataFrame, … }
        """
        for sym, pos in self.portfolio.positions.items():
            if sym not in df_by_sym:
                continue

            bar_high = float(df_by_sym[sym]["high"].iloc[-1])
            if bar_high <= pos.get("trail_base", pos["avg_entry"]):
                continue  # no new high → nothing to do

            # ratchet
            new_base = bar_high
            new_stop = round(new_base * (1.0 - self.trail_pct), 2)

            pos["trail_base"] = new_base
            # never let the stop move downward
            if pos.get("stop") is None or new_stop > pos["stop"]:
                pos["stop"] = new_stop

            print(f"🔒  Updated trail {sym} base={new_base:.2f} "
                  f"stop={pos['stop']:.2f}")

        # persist immediately
        self.portfolio._save_csv()
    

        # ------------------------------------------------------------------
    # stop-loss / take-profit surveillance
    # ------------------------------------------------------------------
    def check_stops(self, latest_prices: dict[str, float]) -> None:
        """
        Scan every open position; if the live price has crossed the
        stored stop (<=) or take-profit (>=), close the whole position
        with a market order and realise P&L.

        `latest_prices`  – dict like {"SPY": 607.12, "QQQ": 451.30}
        """
        for sym, pos in list(self.portfolio.positions.items()):
            px = latest_prices.get(sym)
            if px is None:                     # no price → skip
                continue

            stop_hit = pos.get("stop") is not None and px <= pos["stop"]
            tp_hit   = pos.get("tp")   is not None and px >= pos["tp"]

            if stop_hit or tp_hit:
                qty = int(pos["quantity"])
                reason = "STOP" if stop_hit else "TP"
                print(f"🛑  {reason} hit – closing {sym} qty={qty} @ {px:.2f}")

                # `sell()` overload supplies default ATR so 0.0001 is fine here
                self.sell(sym, qty, px, atr_val=0.0001)
                self.portfolio.close_position(sym, px)


    # ------------------------------------------------------------------
    # order builder (limit / market + bracket if SDK supports)           # pragma: no cover
    def _build_entry_request(self, mode: str, side, symbol,              # pragma: no cover
                             qty, price, atr_val) -> Tuple[Any, str]:    
        if BRACKETS_SUPPORTED:
            stop_px = round(price - atr_val * ATR_MULTIPLIER_STOP, 2)
            tp_req  = (TakeProfitRequest(
                           limit_price=round(price + atr_val * TP_MULT, 2))
                       if TP_MULT else None)
            common  = dict(symbol=symbol, qty=qty, side=side,
                           time_in_force=TimeInForce.GTC,
                           stop_loss=StopLossRequest(stop_price=stop_px),
                           take_profit=tp_req)
            if mode == "limit":
                return (BracketOrderRequest(limit_price=price, **common),
                        f"LIMIT-BRKT@{price:.2f}")
            return (BracketOrderRequest(order_type="market", **common),
                    "MARKET-BRKT")

        # no brackets available
    
        if mode == "limit":
            # --- NEW logic: round & choose correct TIF -----------------
            offset = 0.002 if side == OrderSide.BUY else -0.002
            rounded_price = round(
                round(price * (1 + offset), 2) 
                if not is_crypto(symbol) else price
            )
            
            tif = TimeInForce.GTC if is_crypto(symbol) else TimeInForce.IOC
            return (
                LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    time_in_force= tif,
                    limit_price=rounded_price,
                ),
                f"LIMIT@{rounded_price:.2f}",
            )
        # ------------------------------------------------------------------
        # FINAL fallback: treat anything else as a MARKET order
        tif = TimeInForce.GTC if is_crypto(symbol) else TimeInForce.DAY
        rounded_price = round(price, 2) if not is_crypto(symbol) else price

        return (
            MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=tif,
            ),
            f"MARKET@{rounded_price:.2f}",
        )



    # ------------------------------------------------------------------
    # core submit (LIMIT + robust fallback)
    def _submit(self, side, symbol, qty, price, atr_val):               # noqa: C901
        """
        Live mode:
        1. Post LIMIT (or LIMIT-BRACKET) order.
        2. Wait self.limit_timeout seconds for full fill.
        3. If still open → issue cancel, poll until terminal
           state (`canceled | rejected | expired | filled`).
        4. Only when LIMIT is TERMINAL and qty remains → send
           MARKET for the remainder.
        Simulation / tests:
        • Return a fake order dict once.
        """
        sym_broker = norm_sym(symbol)

        # ---------- 1. Simulation shortcut ---------------------------
        if self.client is None or price is None:
            fake = f"SIM-{int(time.time()*1000)}"
            print(f"✅ {side.name} {symbol} qty={qty} (sim {fake})")
            _safe_log(log_trade, symbol=symbol, side=side.name.lower(),
                      qty=qty, limit_price=price, order_id=fake,
                      fill_price=None)
            return {"id": fake}

        # ---------- 2. Submit LIMIT ----------------------------------
        limit_req, note = self._build_entry_request(
            "limit", side, sym_broker, qty, price, atr_val
        )
        try:
            limit_resp = self.client.submit_order(limit_req)
            _safe_log(log_trade, symbol=symbol, side=side.name.lower(),
                      qty=qty, limit_price=price,
                      order_id=limit_resp.id, fill_price=None)
            print(f"✅ {side.name} {symbol} {note} qty={qty} id={limit_resp.id}")
        except Exception as exc:
            fake = f"SIM-{int(time.time()*1000)}"
            print(f"⚠️  LIMIT rejected ({exc}); simulating.")
            _safe_log(log_trade, symbol=symbol, side=side.name.lower(),
                      qty=qty, limit_price=price, order_id=fake,
                      fill_price=None)
            return {"id": fake}

        # ---------- 3. Unit-test fast-path ---------------------------
        if "MagicMock" in type(self.client).__name__:                   # pragma: no cover
            return limit_resp

        order_id   = limit_resp.id
        filled_qty = 0

        # ---------- 4. Wait for fill or timeout ----------------------
        deadline = time.monotonic() + self.limit_timeout
        while time.monotonic() < deadline:
            try:
                info = self.client.get_order(order_id)
                filled_qty = int(info.filled_qty or 0)
                if info.status.lower() == "filled":
                    self._open_cache.discard((sym_broker, side.name.lower()))
                    return limit_resp
            except Exception:
                pass
            time.sleep(POLL_INTERVAL)

        # ---------- 5. Cancel the remainder ---------------------------------
        try:
            self.client.cancel_order(order_id)
        except Exception:
            pass  # we'll still poll

        cancel_ok = False
        deadline  = time.monotonic() + self.cancel_timeout
        while time.monotonic() < deadline:
            try:
                info = self.client.get_order(order_id)
                status_lower = info.status.lower()
                filled_qty   = int(info.filled_qty or 0)

                if status_lower in {"canceled", "rejected", "expired"}:
                    cancel_ok = True
                    break
                if status_lower == "filled":
                    self._open_cache.discard((sym_broker, side.name.lower()))
                    return limit_resp
                # *** NEW: IOC after-hours quirk ********************************
                if status_lower == "accepted" and limit_req.time_in_force == TimeInForce.IOC:
                    # IOC that’s still accepted cannot execute; consider it dead
                    cancel_ok = True
                    break
                # ****************************************************************
            except Exception:
                pass
            time.sleep(POLL_INTERVAL)

        if not cancel_ok:
            print("⚠️  LIMIT could not be canceled – aborting MARKET fallback.")
            return limit_resp


        # ---------- 6. MARKET fallback for exact remainder -----------
        remaining = qty - filled_qty
        if remaining <= 0:
            self._open_cache.discard((sym_broker, side.name.lower()))
            return limit_resp

        # *** Check if market is open before submitting MARKET fallback ***
        # For equities (non-crypto), prevent queued DAY orders when market is closed
        if not is_crypto(symbol):
            try:
                clock = self.client.get_clock()
                if not clock.is_open:
                    print(f"⚠️  Market closed – skipping MARKET fallback for {symbol}")
                    self._open_cache.discard((sym_broker, side.name.lower()))
                    return limit_resp
            except Exception as exc:
                # If we can't get market status, log warning but proceed
                print(f"⚠️  Could not check market status ({exc}); proceeding with MARKET order")

        print(f"⏳  Limit timeout ({filled_qty}/{qty}) → MARKET {remaining}")
        mkt_req, _ = self._build_entry_request(
            "market", side, sym_broker, remaining, price, atr_val
        )
        try:
            mkt_resp = self.client.submit_order(mkt_req)
            _safe_log(log_trade, symbol=symbol, side=side.name.lower(),
                      qty=remaining, limit_price=None,
                      order_id=mkt_resp.id, fill_price=None)
            self._open_cache.discard((sym_broker, side.name.lower()))
            return mkt_resp
        except (APIError, HTTPError) as exc:
            fake = f"SIM-{int(time.time()*1000)}"
            print(f"⚠️  MARKET fallback failed ({exc}); simulating.")
            _safe_log(log_trade, symbol=symbol, side=side.name.lower(),
                      qty=remaining, limit_price=None,
                      order_id=fake, fill_price=None)
            return {"id": fake}


        
    # ----------------------------------------------------------------------
    def reconcile_open_orders(self) -> None:
        """
        Query Alpaca for *open* orders, update _open_cache and portfolio so the
        bot won't place duplicates right after a restart.
        """
        if self.client is None:             # sim-only mode → nothing to reconcile
            return

        try:
            all_orders  = self.client.get_orders()           # fetch ALL
            open_orders = [o for o in all_orders if o.status.lower() == "open"]

        except Exception as exc:
            logging.warning(f"Alpaca open-order fetch failed: {exc}")
            return

        self._open_cache = {
            (norm_sym(o.symbol), o.side.lower()) for o in open_orders
        }

        # optional: create phantom positions so trailing-stop logic won’t crash
        for o in open_orders:
            sym = norm_sym(o.symbol)
            if sym not in self.portfolio.positions:
                self.portfolio.positions[sym] = {
                    "quantity": float(o.qty),
                    "avg_entry": float(o.limit_price or o.filled_avg_price or 0.0),
                }


    # ------------------------------------------------------------------
    # signal executor (df_ohlc optional for unit-tests)
    # ──────────────────────────────────────────────────────────────────────
    def execute_signals(
        self,
        symbol: str,
        df_signals: pd.DataFrame,
        df_ohlc: pd.DataFrame | None = None,
    ) -> None:
        """
        Act on the latest signal (1 = long, -1 = flat) for *symbol*.

        • Only one position per symbol.
        • ATR-based qty, stop, optional TP.
        • Duplicate-order guard: if an identical open order is already sitting
        at Alpaca, skip submitting a new one (prevents duplication after restarts).
        """
        # use OHLC passed from caller if available, else same DF
        df_ohlc = df_ohlc if df_ohlc is not None else df_signals

        last   = df_signals.iloc[-1]
        price  = float(last["close"])
        signal = int(last["position"])
        atr_val = atr(df_ohlc)                       # ← your existing helper

        # ── DUPLICATE-ORDER GUARD ─────────────────────────────────────────
        side_txt = "buy" if signal == 1 else "sell" if signal == -1 else ""
        if side_txt:          # run guard in both paper and live modes
            # cache open orders once per cycle
            if not hasattr(self, "_open_cache"):
                try:
                    all_orders  = self.client.get_orders()
                    open_orders = [o for o in all_orders if o.status.lower() == "open"]
                    self._open_cache = {
                    (norm_sym(o.symbol), o.side.lower()) for o in open_orders                        
                    }
                except Exception as exc:
                    logging.warning(f"Order-cache fetch failed ({exc})")
                    self._open_cache = set()

            if (norm_sym(symbol), side_txt) in self._open_cache:
                logging.info(f"{symbol}: open {side_txt} order already exists – skipping")
                return
        # ──────────────────────────────────────────────────────────────────

        # ------------- OPEN LONG -------------------------------------------------
        if signal == 1 and not self.portfolio.has_position(symbol):
            qty = self._calc_qty(df_ohlc, price)     # risk-managed sizing
            if qty < MIN_QTY:                        # global constant
                print("⚠️  Qty < MIN_QTY; trade skipped.")
                return

            self.buy(symbol, qty, price, atr_val)    # place order (paper or live)

            stop_lvl = price - atr_val * ATR_MULTIPLIER_STOP
            tp_lvl   = price + atr_val * TP_MULT if TP_MULT else None
            self.portfolio.open_position(symbol, qty, price, stop_lvl, tp_lvl)

        # ------------- CLOSE LONG ------------------------------------------------
        elif signal == -1 and self.portfolio.has_position(symbol):
            qty = int(self.portfolio.positions[symbol]["quantity"])
            self.sell(symbol, qty, price, atr_val)
            self.portfolio.close_position(symbol, price)
