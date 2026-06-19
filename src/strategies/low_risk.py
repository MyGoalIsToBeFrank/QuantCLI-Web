"""
低风险仓位策略

基于 prob_position，但限制最大仓位，从而控制组合最大回撤。
适用于高波动标的或风险厌恶场景。
"""

from typing import Dict, Any
from .base import BaseStrategy


class LowRiskStrategy(BaseStrategy):
    """
    低风险仓位策略。

    与 prob_position 相同，根据 prob_bull 映射目标仓位，
    但将最终仓位限制在 max_position 以内（默认 10%）。
    """

    name = 'low_risk'
    min_prob = 0.3
    max_prob = 1.0
    max_position = 0.1  # 默认最大仓位 10%

    @property
    def accepted_keys(self) -> list:
        return ['prob_bull']

    def decide(self, prediction: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        self.validate(prediction)
        prob = prediction['prob_bull']

        target = (prob - self.min_prob) / (self.max_prob - self.min_prob)
        target = max(0.0, min(1.0, target))

        # 应用仓位上限
        max_pos = context.get('max_position', self.max_position)
        target = min(target, float(max_pos))

        current_pos = context.get('current_position', 0.0)
        threshold = context.get('signal_threshold', 0.10)

        if abs(target - current_pos) < threshold:
            action = 'hold'
            target = current_pos
            note = f'prob_bull={prob:.2f}，目标仓位变化小于{threshold*100:.0f}%，不交易'
        elif target > current_pos:
            action = 'buy'
            note = f'prob_bull={prob:.2f}，低风险目标仓位 {target*100:.1f}%（上限{max_pos*100:.1f}%），买入'
        else:
            action = 'sell'
            note = f'prob_bull={prob:.2f}，低风险目标仓位 {target*100:.1f}%（上限{max_pos*100:.1f}%），卖出'

        return {
            'action': action,
            'target_position': target,
            'note': note
        }
