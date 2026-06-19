"""
组合层（portfolio）：在单股 Pipeline/Strategy/Backtest 之上，
提供账户状态、风险控制与组合级今日决策。

子模块：
  - schema:          共享常量与决策模式定义
  - state:           PortfolioState / Position / 状态读写
  - risk:            回撤事件、风险评分、风险配置
  - quotes:          实时行情快照与校验
  - modes:           按决策模式构造可用数据帧
  - decision_engine: 组合级决策编排
  - reports:         CLI/API/WebUI 友好的格式化
"""

from .schema import (
    DEFAULT_LOT_SIZE,
    DEFAULT_CASH,
    DecisionMode,
)

__all__ = [
    'DEFAULT_LOT_SIZE',
    'DEFAULT_CASH',
    'DecisionMode',
]
