import pandas as pd

from src.backtest.combo_backtester import build_latest_open_decision_frame, build_open_decision_frame


def test_build_open_decision_frame_masks_intraday_ohlcv_to_open():
    raw = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=3, freq="D").date,
        "open": [10.0, 20.0, 30.0],
        "high": [11.0, 25.0, 99.0],
        "low": [9.0, 19.0, 1.0],
        "close": [10.5, 24.0, 80.0],
        "volume": [100, 200, 999],
    })

    decision_df = build_open_decision_frame(raw, current_idx=2)

    latest = decision_df.iloc[-1]
    assert len(decision_df) == 3
    assert latest["open"] == 30.0
    assert latest["high"] == 30.0
    assert latest["low"] == 30.0
    assert latest["close"] == 30.0
    assert latest["volume"] == 0


def test_build_latest_open_decision_frame_appends_open_when_date_is_new():
    raw = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=2, freq="D").date,
        "open": [10.0, 20.0],
        "high": [11.0, 21.0],
        "low": [9.0, 19.0],
        "close": [10.5, 20.5],
        "volume": [100, 200],
    })

    decision_df = build_latest_open_decision_frame(
        raw,
        open_price=30.0,
        decision_date=pd.Timestamp("2026-01-03").date(),
    )

    latest = decision_df.iloc[-1]
    assert len(decision_df) == 3
    assert latest["date"] == pd.Timestamp("2026-01-03").date()
    assert latest["open"] == 30.0
    assert latest["close"] == 30.0
    assert latest["volume"] == 0
