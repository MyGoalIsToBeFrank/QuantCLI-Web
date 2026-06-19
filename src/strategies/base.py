"""
决策策略基类

策略职责：根据 Pipeline 预测结果与上下文，生成当日交易决策。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseStrategy(ABC):
    """
    所有交易策略的基类。

    子类必须实现：
      - name: 类属性，唯一名称
      - accepted_keys: 该策略能处理的 prediction 输出键
      - decide(prediction, context) -> dict

    decide 返回字典：
      {
        'action': 'buy' | 'sell' | 'hold',
        'target_position': float,  # 0.0 ~ 1.0
        'note': str                # 人类可读说明
      }
    """

    name: str = 'base'

    @property
    @abstractmethod
    def accepted_keys(self) -> list:
        """该策略依赖的 prediction 键"""
        pass

    def validate(self, prediction: Dict[str, Any]) -> None:
        missing = [k for k in self.accepted_keys if k not in prediction]
        if missing:
            raise ValueError(f'{self.name} 需要 prediction 键: {missing}')

    @abstractmethod
    def decide(self, prediction: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成交易决策。

        参数:
            prediction: pipeline.predict() 的输出
            context: 包含当前持仓、现金、当日开盘价、前日收盘价、配置等
        """
        pass
