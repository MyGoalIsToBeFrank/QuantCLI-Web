"""
BOLL 均值回归策略

价格触及下轨满仓买入，触及上轨清仓卖出，其余持仓不动。
"""

from typing import Dict, Any
from .base import BaseStrategy


class BollStrategy(BaseStrategy):
    name = 'boll_reversion'

    @property
    def accepted_keys(self) -> list:
        return ['signal', 'boll_upper', 'boll_lower', 'boll_mid']

    def decide(self, prediction: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        self.validate(prediction)
        signal = prediction['signal']

        if signal == 'bull':
            action = 'buy'
            target = 1.0
            note = f'价格触及布林带下轨（lower={prediction["boll_lower"]:.2f}），买入'
        elif signal == 'bear':
            action = 'sell'
            target = 0.0
            note = f'价格触及布林带上轨（upper={prediction["boll_upper"]:.2f}），卖出'
        else:
            action = 'hold'
            target = context.get('current_position', 0.0)
            note = f'价格位于布林带中轨附近（mid={prediction["boll_mid"]:.2f}），持仓不动'

        return {
            'action': action,
            'target_position': target,
            'note': note
        }
