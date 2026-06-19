"""
RSI 阈值策略

RSI < 30 满仓买入，RSI > 70 清仓卖出，其余持仓不动。
"""

from typing import Dict, Any
from .base import BaseStrategy


class RSIStrategy(BaseStrategy):
    name = 'rsi_threshold'
    oversold = 30
    overbought = 70

    @property
    def accepted_keys(self) -> list:
        return ['rsi', 'signal']

    def decide(self, prediction: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        self.validate(prediction)
        rsi = prediction['rsi']
        signal = prediction['signal']

        if rsi < self.oversold:
            action = 'buy'
            target = 1.0
            note = f'RSI={rsi:.1f} < {self.oversold}，超卖，满仓买入'
        elif rsi > self.overbought:
            action = 'sell'
            target = 0.0
            note = f'RSI={rsi:.1f} > {self.overbought}，超买，清仓卖出'
        else:
            action = 'hold'
            target = context.get('current_position', 0.0)
            note = f'RSI={rsi:.1f} 处于中性区间，持仓不动'

        return {
            'action': action,
            'target_position': target,
            'note': note
        }
