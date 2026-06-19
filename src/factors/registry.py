#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FactorRegistry：标准化因子注册表

所有因子（feature）集中在此注册，包含：
  - 唯一名称
  - 所需原始列
  - 默认参数
  - 标准计算函数
  - 人类可读说明

Pipeline 配置通过引用 factor_id + params 来声明自己使用哪些因子，
无需在 Pipeline 类中硬编码计算逻辑。
"""

from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
import inspect


@dataclass
class FactorMeta:
    name: str
    required_columns: List[str]
    default_params: Dict[str, Any]
    compute: Callable
    description: str = ''


class FactorRegistry:
    def __init__(self):
        self._factors: Dict[str, FactorMeta] = {}

    def register(
        self,
        name: str,
        required_columns: List[str],
        default_params: Optional[Dict[str, Any]] = None,
        description: str = ''
    ) -> Callable:
        """
        装饰器注册因子。

        用法：
            @FACTOR_REGISTRY.register(
                name='sma',
                required_columns=['close'],
                default_params={'window': 20},
                description='简单移动平均'
            )
            def compute_sma(df, window=20):
                return df['close'].rolling(window=window).mean()
        """
        default_params = default_params or {}

        def decorator(func: Callable) -> Callable:
            self._factors[name] = FactorMeta(
                name=name,
                required_columns=required_columns,
                default_params=default_params,
                compute=func,
                description=description
            )
            return func
        return decorator

    def get(self, name: str) -> FactorMeta:
        if name not in self._factors:
            raise KeyError(f'未注册的因子: {name}')
        return self._factors[name]

    def list(self) -> List[Dict[str, Any]]:
        return [
            {
                'name': m.name,
                'required_columns': m.required_columns,
                'default_params': m.default_params,
                'description': m.description
            }
            for m in self._factors.values()
        ]

    def compute(self, df, factor_spec: Dict[str, Any]) -> Any:
        """
        根据因子规格计算因子序列。

        factor_spec 格式：
            {
                'name': 'sma',
                'params': {'window': 5},      # 可选，覆盖默认参数
                'output_col': 'sma5'          # 可选，用于标识输出列
            }
        """
        name = factor_spec['name']
        meta = self.get(name)
        params = dict(meta.default_params)
        if 'params' in factor_spec and factor_spec['params']:
            params.update(factor_spec['params'])

        # 检查所需列
        missing = [c for c in meta.required_columns if c not in df.columns]
        if missing:
            raise ValueError(f'因子 {name} 缺少必要列: {missing}')

        result = meta.compute(df, **params)
        return result

    def compute_many(self, df, factor_specs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量计算多个因子，返回 {output_col: series} 字典"""
        out = {}
        for spec in factor_specs:
            series = self.compute(df, spec)
            col = spec.get('output_col') or spec['name']
            out[col] = series
        return out


# 全局注册表实例
FACTOR_REGISTRY = FactorRegistry()
