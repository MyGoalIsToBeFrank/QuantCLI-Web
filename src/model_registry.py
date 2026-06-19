"""
模型注册表

统一管理所有可替换预测模型。
"""

from src.registry_base import SimpleRegistry
from src.models.base import BaseModel
from src.models.dual_logistic import DualLogisticModel
from src.models.logistic import LogisticModel
from src.models.dual_random_forest import DualRandomForestModel
from src.models.random_forest import RandomForestModel
from src.models.macd_rule import MacdRuleModel
from src.models.rsi_rule import RsiRuleModel
from src.models.boll_rule import BollRuleModel


class ModelRegistry(SimpleRegistry[BaseModel]):
    def __init__(self):
        super().__init__()
        for cls in [
            DualLogisticModel,
            LogisticModel,
            DualRandomForestModel,
            RandomForestModel,
            MacdRuleModel,
            RsiRuleModel,
            BollRuleModel,
        ]:
            self.register(cls)


# 全局实例
MODEL_REGISTRY = ModelRegistry()
