"""
MACD 金叉死叉策略

金叉买入，死叉卖出。
"""

from typing import Dict, Any
from .base import BaseStrategy


class MacdStrategy(BaseStrategy):
    name = 'macd_cross'

    @property
    def accepted_keys(self) -> list:
        return ['signal', 'dif', 'dea', 'hist']

    def decide(self, prediction: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        self.validate(prediction)
        signal = prediction['signal']

        if signal == 'bull':
            action = 'buy'
            target = 1.0
            note = f'MACD 金叉（dif={prediction["dif"]:.3f}, dea={prediction["dea"]:.3f}），买入'
        elif signal == 'bear':
            action = 'sell'
            target = 0.0
            note = f'MACD 死叉（dif={prediction["dif"]:.3f}, dea={prediction["dea"]:.3f}），卖出'
        else:
            action = 'hold'
            target = context.get('current_position', 0.0)
            note = f'MACD 无交叉（hist={prediction["hist"]:.3f}），持仓不动'

        return {
            'action': action,
            'target_position': target,
            'note': note
        }
