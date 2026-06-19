#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型基类。

每个模型自己决定如何读取 config、如何 fit、如何 predict。
Pipeline 只负责：
  1. 准备因子 / 目标 DataFrame
  2. 把 config 传给模型
  3. 调用 model.fit(df) / model.predict(row)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd


class BaseModel(ABC):
    name: str = 'base'

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_fitted = False

    def model_params(self) -> Dict[str, Any]:
        """Return model-specific params, with legacy `params` compatibility."""
        return self.config.get('model_params') or self.config.get('params', {})

    @abstractmethod
    def fit(self, df: pd.DataFrame) -> None:
        """在 df 上训练模型，df 已包含 feature_cols 与 target 列"""
        pass

    @abstractmethod
    def predict(self, row: pd.Series) -> Dict[str, Any]:
        """对单行数据预测，返回至少包含 prob_bull / score / signal 的 dict"""
        pass

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'BaseModel':
        """子类可覆盖，以不同方式读取 config"""
        return cls(config)
