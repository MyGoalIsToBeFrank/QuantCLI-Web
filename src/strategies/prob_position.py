"""
概率仓位策略

基于 pipeline 输出的 prob_bull 映射到目标仓位：
  prob_bull <= 0.3 -> 空仓
  prob_bull >= 1.0 -> 满仓
  中间线性插值
"""

from typing import Dict, Any
from .base import BaseStrategy


class ProbPositionStrategy(BaseStrategy):
    name = 'prob_position'
    min_prob = 0.3
    max_prob = 1.0

    @property
    def accepted_keys(self) -> list:
        return ['prob_bull']

    def decide(self, prediction: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        self.validate(prediction)
        prob = prediction['prob_bull']

        target = (prob - self.min_prob) / (self.max_prob - self.min_prob)
        target = max(0.0, min(1.0, target))

        current_pos = context.get('current_position', 0.0)
        threshold = context.get('signal_threshold', 0.10)

        if abs(target - current_pos) < threshold:
            action = 'hold'
            target = current_pos
            note = f'prob_bull={prob:.2f}，目标仓位变化小于{threshold*100:.0f}%，不交易'
        elif target > current_pos:
            action = 'buy'
            note = f'prob_bull={prob:.2f}，目标仓位 {target*100:.1f}%，买入'
        else:
            action = 'sell'
            note = f'prob_bull={prob:.2f}，目标仓位 {target*100:.1f}%，卖出'

        return {
            'action': action,
            'target_position': target,
            'note': note
        }
