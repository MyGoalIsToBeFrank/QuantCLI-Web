from datetime import datetime, timezone, timedelta

import pandas as pd
import pytest

from src.portfolio.modes import (
    build_close_frame, build_open_frame, build_late_session_frame, build_mode_frame,
)
from src.portfolio.quotes import QuoteSnapshot
from src.portfolio.schema import DecisionMode

_CST = timezone(timedelta(hours=8))


def _raw():
    return pd.DataFrame({
        'date': pd.date_range('2026-06-15', periods=3, freq='D').date,
        'open': [10.0, 11.0, 12.0],
        'high': [10.5, 11.5, 12.5],
        'low': [9.8, 10.8, 11.8],
        'close': [10.2, 11.2, 12.2],
        'volume': [1000, 1100, 1200],
    })


def test_close_after_market_uses_complete_bars():
    mf = build_close_frame(_raw())
    assert len(mf.frame) == 3
    # 完整日线未被遮蔽
    assert mf.frame['high'].iloc[-1] == 12.5
    assert mf.reference_price == 12.2
    assert mf.prev_close == 11.2
    assert mf.mode == DecisionMode.CLOSE_AFTER_MARKET


def test_open_realtime_masks_current_row_to_open():
    raw = _raw()
    new_date = pd.Timestamp('2026-06-19').date()
    mf = build_open_frame(raw, open_price=13.0, decision_date=new_date)
    latest = mf.frame.iloc[-1]
    assert latest['open'] == 13.0
    assert latest['high'] == 13.0
    assert latest['low'] == 13.0
    assert latest['close'] == 13.0
    assert latest['volume'] == 0
    assert mf.reference_price == 13.0
    assert mf.prev_close == 12.2


def test_late_session_appends_snapshot_row():
    raw = _raw()
    ts = datetime.now(_CST).replace(microsecond=0).isoformat()
    snap = QuoteSnapshot(
        symbol='002156.SZ', timestamp=ts, price=13.5, open=12.8,
        high=13.8, low=12.6, prev_close=12.2, volume=5000,
    )
    mf = build_late_session_frame(raw, snap)
    latest = mf.frame.iloc[-1]
    assert latest['close'] == 13.5  # 当前价作为 close 代理
    assert latest['open'] == 12.8
    assert latest['volume'] == 5000
    assert mf.reference_price == 13.5
    assert mf.mode == DecisionMode.LATE_SESSION


def test_late_session_rejects_stale_snapshot():
    raw = _raw()
    old_ts = (datetime.now(_CST) - timedelta(hours=5)).replace(microsecond=0).isoformat()
    snap = QuoteSnapshot(
        symbol='002156.SZ', timestamp=old_ts, price=13.5, open=12.8,
        high=13.8, low=12.6, prev_close=12.2,
    )
    with pytest.raises(ValueError):
        build_late_session_frame(raw, snap, max_age_minutes=120.0)


def test_late_session_rejects_invalid_snapshot():
    raw = _raw()
    ts = datetime.now(_CST).isoformat()
    # price 超出 [low, high]
    snap = QuoteSnapshot(
        symbol='002156.SZ', timestamp=ts, price=99.0, open=12.8,
        high=13.8, low=12.6, prev_close=12.2,
    )
    with pytest.raises(ValueError):
        build_late_session_frame(raw, snap)


def test_build_mode_frame_dispatch():
    raw = _raw()
    mf = build_mode_frame(DecisionMode.CLOSE_AFTER_MARKET, raw)
    assert mf.mode == DecisionMode.CLOSE_AFTER_MARKET

    with pytest.raises(ValueError):
        build_mode_frame(DecisionMode.LATE_SESSION, raw)  # 缺 snapshot
