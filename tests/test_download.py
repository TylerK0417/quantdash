from src.download import fetch


def test_row_count():
    # Fetch 2024-01-02 → 2024-01-05 for SPY at daily bars
    tbl = fetch("SPY", "2024-01-02", "2024-01-05", "1Day")
    # Jan 2, 3, 4 are trading days (3 rows)
    assert tbl.num_rows == 3


def test_columns_exist():
    tbl = fetch("SPY", "2024-01-02", "2024-01-05", "1Day")
    # Check that the OHLCV columns are present
    for col in ("open", "high", "low", "close", "volume"):
        assert col in tbl.column_names
