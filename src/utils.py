# src/utils.py
def norm_sym(raw: str) -> str:
    """BTC/USD → BTCUSD, eth-usd → ETHUSD, AAPL → AAPL"""
    return raw.strip().upper().replace("/", "").replace("-", "").replace("_", "")

# ── crypto helper -------------------------------------------------------
def is_crypto(sym: str) -> bool:
    """
    Very loose check: returns True when the symbol looks like a crypto pair
    we trade (BTCUSD, ETHUSD, BTC/USDT, etc.).
    """
    sym_up = sym.upper().replace("/", "")
    return sym_up.endswith(("USD", "USDT")) and len(sym_up) > 5

