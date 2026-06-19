#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TargetRegistry：标准化监督目标注册表

用于生成模型训练所需的标签（y），例如：
  - 未来 N 日收盘价是否上涨
  - 未来 N 日均线方向
  - 未来 N 日收益率分桶
  - 未来 N 日波动率是否超过阈值

与 FactorRegistry 分离，语义更清晰：
  - FactorRegistry: 输入特征 X
  - TargetRegistry: 监督目标 y
"""

from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class TargetMeta:
    name: str
    required_columns: List[str]
    default_params: Dict[str, Any]
    compute: Callable
    description: str = ''


class TargetRegistry:
    def __init__(self):
        self._targets: Dict[str, TargetMeta] = {}

    def register(
        self,
        name: str,
        required_columns: List[str],
        default_params: Optional[Dict[str, Any]] = None,
        description: str = ''
    ) -> Callable:
        default_params = default_params or {}

        def decorator(func: Callable) -> Callable:
            self._targets[name] = TargetMeta(
                name=name,
                required_columns=required_columns,
                default_params=default_params,
                compute=func,
                description=description
            )
            return func
        return decorator

    def get(self, name: str) -> TargetMeta:
        if name not in self._targets:
            raise KeyError(f'未注册的目标: {name}')
        return self._targets[name]

    def list(self) -> List[Dict[str, Any]]:
        return [
            {
                'name': m.name,
                'required_columns': m.required_columns,
                'default_params': m.default_params,
                'description': m.description
            }
            for m in self._targets.values()
        ]

    def compute(self, df, target_spec: Dict[str, Any]) -> Any:
        name = target_spec['name']
        meta = self.get(name)
        params = dict(meta.default_params)
        if 'params' in target_spec and target_spec['params']:
            params.update(target_spec['params'])

        missing = [c for c in meta.required_columns if c not in df.columns]
        if missing:
            raise ValueError(f'目标 {name} 缺少必要列: {missing}')

        return meta.compute(df, **params)


# 全局实例
TARGET_REGISTRY = TargetRegistry()
