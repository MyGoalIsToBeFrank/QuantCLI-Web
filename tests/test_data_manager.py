from datetime import date

import pandas as pd

from src.data import data_manager


def test_download_yfinance_preserves_close_and_adj_close(monkeypatch):
    raw = pd.DataFrame({
        "Date": [pd.Timestamp("2026-06-18")],
        "Open": [10.0],
        "High": [12.0],
        "Low": [9.5],
        "Close": [11.0],
        "Adj Close": [8.0],
        "Volume": [1000],
    })

    monkeypatch.setattr(data_manager.yyf, "download", lambda *args, **kwargs: raw)

    df = data_manager._download_yfinance("TEST", "2026-06-18", "2026-06-19")

    assert float(df["close"].iloc[0]) == 11.0
    assert float(df["adj_close"].iloc[0]) == 8.0


def test_verify_stock_data_reports_network_failure_without_writing(monkeypatch):
    monkeypatch.setattr(data_manager, "_download_yfinance", lambda *args, **kwargs: None)

    result = data_manager.verify_stock_data("002156.SZ", days=3)

    assert result["success"] is False
    assert result["symbol"] == "002156.SZ"
    assert "download" in result["message"].lower()
