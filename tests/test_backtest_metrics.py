import pandas as pd
import pytest

from src.backtest.metrics import calculate_metrics


def test_calculate_metrics_includes_buy_hold_baseline():
    records = pd.DataFrame({
        "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
        "open": [10.0, 12.0, 11.0],
        "close": [12.0, 11.0, 15.0],
        "shares": [0, 0, 0],
        "portfolio": [100.0, 110.0, 120.0],
        "total_fees": [0.0, 0.0, 0.0],
    })

    metrics = calculate_metrics(records, initial_capital=100.0)

    assert metrics["total_return_pct"] == pytest.approx(20.0)
    assert metrics["buy_hold_return_pct"] == 50.0
    assert abs(metrics["buy_hold_max_drawdown_pct"] - (-8.333333333333332)) < 1e-12
    assert metrics["excess_return_pct"] == pytest.approx(-30.0)
