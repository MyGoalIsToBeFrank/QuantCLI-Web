#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
正则化双随机森林 MA Pipeline

基于配置 rf_ma_dual_v1：
  - 与 ma_dual 完全相同的特征与目标
  - 用两颗 max_depth=3 的随机森林分别预测 MA5/MA20 方向
  - 加权综合概率
"""

from .configurable import ConfigurablePipeline


class RFMADualPipeline(ConfigurablePipeline):
    name = 'rf_ma_dual'
    config_id = 'rf_ma_dual_v1'

    def __init__(self):
        super().__init__(config_id=self.config_id, name=self.name)
