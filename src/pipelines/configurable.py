#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ConfigurablePipeline：通用可配置 Pipeline

职责：
  1. 按配置计算因子与目标
  2. 从 ModelRegistry 获取模型并训练
  3. 调用模型 predict 输出信号

模型实现完全解耦到 src/models/。
"""

from typing import List, Dict, Any
import pandas as pd

from src.pipeline_configs import PIPELINE_CONFIG_MANAGER
from src.model_registry import MODEL_REGISTRY
from src.factors.registry import FACTOR_REGISTRY
from src.factors.definitions import *  # noqa: F401,F403
from src.factors.target_registry import TARGET_REGISTRY
from src.factors.target_definitions import *  # noqa: F401,F403
from .base import BasePipeline


class ConfigurablePipeline(BasePipeline):
    """
    通用可配置 Pipeline。

    子类只需指定 name 与 config_id：
        class MADualPipeline(ConfigurablePipeline):
            name = 'ma_dual'
            config_id = 'ma_dual_v1'
    """

    def __init__(self, config_id: str, name: str = None):
        self.config_id = config_id
        self.name = name or config_id
        self.config = PIPELINE_CONFIG_MANAGER.get(config_id)
        self.df_model = None
        self.df_features = None
        self.model = None

    @property
    def required_columns(self) -> List[str]:
        return ['date', 'open', 'high', 'low', 'close', 'volume']

    @property
    def output_keys(self) -> List[str]:
        return list(self.config.get('predictions', {}).keys())

    def validate(self, raw_df: pd.DataFrame) -> None:
        missing = [c for c in self.required_columns if c not in raw_df.columns]
        if missing:
            raise ValueError(f'{self.name} 缺少列: {missing}')

    def _compute_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for spec in self.config.get('factors', []):
            result = FACTOR_REGISTRY.compute(df, spec)
            if isinstance(result, pd.DataFrame):
                for col in result.columns:
                    df[col] = result[col]
            else:
                out_col = spec.get('output_col') or spec['name']
                df[out_col] = result
        return df

    def _compute_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        for spec in self.config.get('targets', []):
            result = TARGET_REGISTRY.compute(df, spec)
            out_col = spec.get('output_col') or spec['name']
            df[out_col] = result
        return df

    def fit(self, raw_df: pd.DataFrame, end_idx: int = None) -> None:
        self.validate(raw_df)
        df = raw_df.copy().reset_index(drop=True)
        if end_idx is not None:
            df = df.iloc[:end_idx].copy()

        df = self._compute_factors(df)
        df = self._compute_targets(df)

        feature_cols = self.config.get('feature_cols', [])
        target_cols = [
            spec.get('output_col') or spec['name']
            for spec in self.config.get('targets', [])
        ]
        self.df_features = df.dropna(subset=feature_cols).reset_index(drop=True)
        train_subset = feature_cols + target_cols
        if train_subset:
            df_train = df.dropna(subset=train_subset).reset_index(drop=True)
        else:
            df_train = self.df_features.copy()
        self.df_model = df_train

        if len(df_train) < 60:
            return

        model_type = self.config['model']['type']
        model_config = self.config['model'].get('params', {})
        # 把 feature_cols / targets 等也交给模型自己读取
        full_model_config = {
            **self.config,
            'model_params': model_config,
            'model_type': model_type
        }
        self.model = MODEL_REGISTRY.create(model_type, full_model_config)
        self.model.fit(df_train)

    def predict(self, idx: int = None) -> Dict[str, Any]:
        if self.df_features is None or self.model is None:
            raise RuntimeError('请先调用 fit()')
        if idx is None:
            idx = len(self.df_features) - 1
        row = self.df_features.iloc[idx]
        return self.model.predict(row)
