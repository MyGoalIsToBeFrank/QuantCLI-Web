"""
策略注册表

统一管理所有可替换交易策略。
"""

from typing import List

from src.registry_base import SimpleRegistry
from src.strategies.base import BaseStrategy
from src.strategies.rsi_threshold import RSIStrategy
from src.strategies.boll_reversion import BollStrategy
from src.strategies.macd_cross import MacdStrategy
from src.strategies.prob_position import ProbPositionStrategy
from src.strategies.low_risk import LowRiskStrategy


class StrategyRegistry(SimpleRegistry[BaseStrategy]):
    def __init__(self):
        super().__init__()
        for cls in [
            RSIStrategy,
            BollStrategy,
            MacdStrategy,
            ProbPositionStrategy,
            LowRiskStrategy,
        ]:
            self.register(cls)

    def list_info(self) -> List[dict]:
        return [
            {'name': name, 'accepted_keys': cls().accepted_keys}
            for name, cls in self.list_items().items()
        ]


# 全局实例
STRATEGY_REGISTRY = StrategyRegistry()
