"""
按决策模式构造可用数据帧

核心不变量：market timing 决定哪些数据合法可用。
  - close_after_market: 仅完整日线
  - open_realtime: 允许 T 开盘价，禁止 T 收/高/低（复用 build_latest_open_decision_frame）
  - late_session: 仅允许提供的行情快照字段

每个构造器返回 ModeFrame，携带用于成交参考的价格与前收盘价。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd

from src.backtest.combo_backtester import build_latest_open_decision_frame
from .schema import DecisionMode
from .quotes import QuoteSnapshot


@dataclass
class ModeFrame:
    """模式数据帧及其执行参考信息。"""

    frame: pd.DataFrame          # 供 pipeline.fit 使用的数据
    reference_price: float       # 建议成交参考价
    prev_close: float            # 前一交易日收盘价
    decision_date: object        # 决策日
    mode: str


def _last_date(raw_df: pd.DataFrame):
    return raw_df['date'].iloc[-1]


def build_close_frame(raw_df: pd.DataFrame) -> ModeFrame:
    """盘后模式：使用完整日线，参考价为最新收盘价。"""
    frame = raw_df.copy().reset_index(drop=True)
    ref = float(frame['close'].iloc[-1])
    prev_close = float(frame['close'].iloc[-2]) if len(frame) > 1 else ref
    return ModeFrame(
        frame=frame,
        reference_price=ref,
        prev_close=prev_close,
        decision_date=_last_date(frame),
        mode=DecisionMode.CLOSE_AFTER_MARKET,
    )


def build_open_frame(raw_df: pd.DataFrame, open_price: float,
                     decision_date=None) -> ModeFrame:
    """开盘实时模式：仅暴露已知 T 开盘价，T 收/高/低被遮蔽。"""
    if open_price is None or float(open_price) <= 0:
        raise ValueError('open_realtime 模式需要正的开盘价 open_price')
    if decision_date is None:
        decision_date = _last_date(raw_df)
    frame = build_latest_open_decision_frame(raw_df, float(open_price), decision_date)
    # 前收盘价：若 raw_df 最新行就是决策日，则其前一行收盘；否则为最新收盘
    if str(_last_date(raw_df)) == str(decision_date) and len(raw_df) > 1:
        prev_close = float(raw_df['close'].iloc[-2])
    else:
        prev_close = float(raw_df['close'].iloc[-1])
    return ModeFrame(
        frame=frame,
        reference_price=float(open_price),
        prev_close=prev_close,
        decision_date=decision_date,
        mode=DecisionMode.OPEN_REALTIME,
    )


def build_late_session_frame(raw_df: pd.DataFrame, snapshot: QuoteSnapshot,
                             max_age_minutes: float = 120.0,
                             reject_stale: bool = True) -> ModeFrame:
    """尾盘模式：以行情快照构造/替换决策日数据行。

    只使用快照提供的字段（open/high/low/price/volume），不窥视未来收盘。
    当前价 price 作为当日 close 的代理。
    """
    snapshot.validate()
    if reject_stale and snapshot.is_stale(max_age_minutes):
        raise ValueError(f'{snapshot.symbol} 行情快照已过期（>{max_age_minutes}分钟）')

    decision_date = _parse_snapshot_date(snapshot)
    base = raw_df.copy().reset_index(drop=True)

    row = {
        'date': decision_date,
        'open': float(snapshot.open),
        'high': float(snapshot.high),
        'low': float(snapshot.low),
        'close': float(snapshot.price),
        'volume': float(snapshot.volume),
    }

    if str(_last_date(base)) == str(decision_date):
        last = len(base) - 1
        for key, value in row.items():
            base.loc[last, key] = value
        prev_close = float(base['close'].iloc[-2]) if len(base) > 1 else float(snapshot.prev_close)
        frame = base
    else:
        prev_close = float(base['close'].iloc[-1]) if len(base) else float(snapshot.prev_close)
        frame = pd.concat([base, pd.DataFrame([row])], ignore_index=True)

    return ModeFrame(
        frame=frame,
        reference_price=float(snapshot.price),
        prev_close=prev_close,
        decision_date=decision_date,
        mode=DecisionMode.LATE_SESSION,
    )


def _parse_snapshot_date(snapshot: QuoteSnapshot):
    """从快照 timestamp 中取决策日。"""
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(snapshot.timestamp)).date()
    except (ValueError, TypeError):
        return None


def build_mode_frame(mode: str, raw_df: pd.DataFrame,
                     open_price: float = None,
                     snapshot: QuoteSnapshot = None,
                     decision_date=None,
                     max_age_minutes: float = 120.0,
                     reject_stale: bool = True) -> ModeFrame:
    """按模式分派到对应构造器。"""
    DecisionMode.validate(mode)
    if mode == DecisionMode.CLOSE_AFTER_MARKET:
        return build_close_frame(raw_df)
    if mode == DecisionMode.OPEN_REALTIME:
        return build_open_frame(raw_df, open_price, decision_date)
    if mode == DecisionMode.LATE_SESSION:
        if snapshot is None:
            raise ValueError('late_session 模式需要行情快照 snapshot')
        return build_late_session_frame(raw_df, snapshot,
                                        max_age_minutes=max_age_minutes,
                                        reject_stale=reject_stale)
    raise ValueError(f'未实现的模式: {mode}')  # pragma: no cover
