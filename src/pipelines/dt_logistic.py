#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DT + Logistic Pipeline

基于配置 dt_logistic_v1：
  - 使用 FactorRegistry 计算基础因子 + 滚动决策树概率因子 dt_prob
  - 使用 logistic 模型预测未来 5 日方向
"""

from .configurable import ConfigurablePipeline


class DTLogisticPipeline(ConfigurablePipeline):
    name = 'dt_logistic'
    config_id = 'dt_logistic_v1'

    def __init__(self):
        super().__init__(config_id=self.config_id, name=self.name)
