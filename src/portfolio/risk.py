"""
组合风险度量与风险配置

包含：
  - count_drawdown_events: 回撤事件计数（定义经测试固化）
  - 最大回撤 / 近期波动率等度量
  - RiskProfile / RiskProfileManager: 风险配置读写与默认值
  - score_candidate: 风险优先的候选评分（暴露各分量，可解释）

回撤事件定义：
  - 当权益自峰值回撤跌破 -drawdown_event_threshold_pct 时，事件开始。
  - 当权益回升至距前峰值 recovery_pct(默认 1%) 以内，或创出新峰值时，事件结束。
  - 统计窗口内的事件总数。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Sequence, Optional

from .schema import SCHEMA_VERSION


# ============================================================
# 回撤与波动度量
# ============================================================

def count_drawdown_events(equity: Sequence[float],
                          threshold_pct: float = 3.0,
                          recovery_pct: float = 1.0) -> int:
    """统计权益曲线中的回撤事件数。

    参数:
        equity: 权益（或价格）序列
        threshold_pct: 触发事件的回撤阈值（正数，单位 %）
        recovery_pct: 视为回撤结束的回升阈值（距峰值 % 以内）
    """
    values = [float(v) for v in equity if v is not None]
    if len(values) < 2:
        return 0

    peak = values[0]
    in_event = False
    count = 0
    for v in values:
        if v > peak:
            peak = v
            in_event = False
            continue
        if peak <= 0:
            continue
        drawdown_pct = (v - peak) / peak * 100.0  # <= 0
        if not in_event and drawdown_pct <= -abs(threshold_pct):
            in_event = True
            count += 1
        elif in_event and drawdown_pct >= -abs(recovery_pct):
            in_event = False
    return count


def max_drawdown_pct(equity: Sequence[float]) -> float:
    """返回最大回撤（负数，单位 %）。"""
    values = [float(v) for v in equity if v is not None]
    if len(values) < 2:
        return 0.0
    peak = values[0]
    worst = 0.0
    for v in values:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (v - peak) / peak * 100.0
            if dd < worst:
                worst = dd
    return worst


def recent_volatility(closes: Sequence[float], window: int = 20) -> float:
    """近 window 日收益率标准差（日波动率）。"""
    values = [float(v) for v in closes if v is not None]
    if len(values) < 3:
        return 0.0
    tail = values[-(window + 1):] if window > 0 else values
    returns = []
    for prev, cur in zip(tail[:-1], tail[1:]):
        if prev > 0:
            returns.append(cur / prev - 1.0)
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return var ** 0.5


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# ============================================================
# 风险配置
# ============================================================

@dataclass
class RiskProfile:
    """组合风险控制参数。默认值刻意保守。"""

    max_total_position: float = 0.40
    max_single_position: float = 0.10
    max_late_session_position: float = 0.20
    min_cash_ratio: float = 0.20
    drawdown_limit_pct: float = 5.0
    drawdown_event_threshold_pct: float = 3.0
    max_drawdown_events: int = 3
    rebalance_threshold: float = 0.05
    late_session_take_profit_pct: float = 2.0
    late_session_exit: str = 'next_day_tail_if_not_hit'
    # 风险度量回看窗口（交易日）；用于把"历史回撤"限定在近期可比区间。
    risk_lookback_days: int = 120
    # 单股近窗口价格最大回撤硬性上限（%）。注意 drawdown_limit_pct 面向组合权益，
    # 而个股价格回撤天然更大，故单独设置更现实的个股阈值。
    single_drawdown_limit_pct: float = 25.0
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RiskProfile':
        fields = cls().__dict__.keys()
        clean = {k: v for k, v in (data or {}).items() if k in fields}
        return cls(**clean)


class RiskProfileManager:
    """风险配置读写；缺失文件时返回保守默认值。"""

    def __init__(self, path: Path = None):
        self.path = Path(path) if path else Path('data/portfolio_risk_profile.json')

    def load(self) -> RiskProfile:
        if not self.path.exists():
            return RiskProfile()
        with open(self.path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return RiskProfile.from_dict(data)

    def save(self, profile: RiskProfile) -> RiskProfile:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
        return profile

    def update(self, **kwargs) -> RiskProfile:
        profile = self.load()
        for key, value in kwargs.items():
            if value is None:
                continue
            if not hasattr(profile, key):
                raise ValueError(f'未知风险参数: {key}')
            setattr(profile, key, value)
        return self.save(profile)


# ============================================================
# 风险优先候选评分
# ============================================================

# 用于归一化的经验上限
_VOLATILITY_CAP = 0.05  # 5% 日波动视为高波动上限


def score_candidate(metrics: Dict[str, Any],
                    prediction: Dict[str, Any],
                    profile: RiskProfile) -> Dict[str, Any]:
    """根据风险度量与预测计算可解释的评分分量。

    返回 dict，包含 risk_score、opportunity_score、final_rank 与各归一化分量。
    final_rank 越大越优先。风险过滤（硬性拒绝）由上层处理，本函数只算分。
    """
    max_dd = abs(float(metrics.get('max_drawdown_pct', 0.0)))
    dd_events = int(metrics.get('drawdown_events', 0))
    volatility = float(metrics.get('recent_volatility', 0.0))
    liquidity_penalty = float(metrics.get('liquidity_penalty', 0.0))

    dd_norm_base = getattr(profile, 'single_drawdown_limit_pct', None) or profile.drawdown_limit_pct
    norm_max_dd = _clamp(max_dd / dd_norm_base) if dd_norm_base > 0 else 0.0
    norm_dd_events = _clamp(dd_events / max(1, profile.max_drawdown_events))
    norm_volatility = _clamp(volatility / _VOLATILITY_CAP)
    norm_liquidity_penalty = _clamp(liquidity_penalty)

    risk_score = (
        0.45 * norm_max_dd
        + 0.25 * norm_dd_events
        + 0.15 * norm_volatility
        + 0.15 * norm_liquidity_penalty
    )

    prob_bull = float(prediction.get('prob_bull', 0.5))
    signal = str(prediction.get('signal', 'neutral'))
    prediction_strength = _clamp((prob_bull - 0.5) * 2.0)
    if signal == 'bull':
        trend_confirmation = 1.0
    elif signal == 'bear':
        trend_confirmation = 0.0
    else:
        trend_confirmation = 0.5
    liquidity_score = _clamp(1.0 - norm_liquidity_penalty)

    opportunity_score = (
        0.60 * prediction_strength
        + 0.25 * trend_confirmation
        + 0.15 * liquidity_score
    )

    final_rank = opportunity_score - risk_score

    return {
        'risk_score': round(risk_score, 4),
        'opportunity_score': round(opportunity_score, 4),
        'final_rank': round(final_rank, 4),
        'components': {
            'normalized_max_drawdown': round(norm_max_dd, 4),
            'normalized_drawdown_events': round(norm_dd_events, 4),
            'normalized_recent_volatility': round(norm_volatility, 4),
            'liquidity_penalty': round(norm_liquidity_penalty, 4),
            'prediction_strength': round(prediction_strength, 4),
            'trend_confirmation': round(trend_confirmation, 4),
            'liquidity_score': round(liquidity_score, 4),
        },
    }
