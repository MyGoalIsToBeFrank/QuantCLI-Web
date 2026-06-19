#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MA 双模型 Pipeline

基于配置 ma_dual_v1：
  - 使用 FactorRegistry 计算单股票因子
  - 训练两个 LogisticRegression 预测 MA5/MA20 方向
  - 加权综合概率
"""

from .configurable import ConfigurablePipeline


class MADualPipeline(ConfigurablePipeline):
    name = 'ma_dual'
    config_id = 'ma_dual_v1'

    def __init__(self):
        super().__init__(config_id=self.config_id, name=self.name)
