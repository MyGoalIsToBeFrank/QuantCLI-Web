"""
Pipeline 注册表

统一管理所有可替换预测管线。
"""

from typing import List

from src.registry_base import SimpleRegistry
from src.pipelines.base import BasePipeline
from src.pipelines.rsi import RSIPipeline
from src.pipelines.boll import BollPipeline
from src.pipelines.macd import MacdPipeline
from src.pipelines.ma_dual import MADualPipeline
from src.pipelines.dt_logistic import DTLogisticPipeline
from src.pipelines.rf_ma_dual import RFMADualPipeline


class PipelineRegistry(SimpleRegistry[BasePipeline]):
    def __init__(self):
        super().__init__()
        for cls in [
            RSIPipeline,
            BollPipeline,
            MacdPipeline,
            MADualPipeline,
            DTLogisticPipeline,
            RFMADualPipeline,
        ]:
            self.register(cls)

    def get_config_id(self, name: str) -> str:
        """获取 Pipeline 对应的配置 ID"""
        cls = self.get(name)
        return getattr(cls, 'config_id', name)

    def list_info(self) -> List[dict]:
        return [
            {
                'name': name,
                'config_id': getattr(cls, 'config_id', name),
                'required_columns': cls().required_columns,
                'output_keys': cls().output_keys,
            }
            for name, cls in self.list_items().items()
        ]


# 全局实例
PIPELINE_REGISTRY = PipelineRegistry()
