#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BestComboRegistry：最佳组合注册表

持久化每只股票的最佳组合，格式为：
  {
    "symbol": {
      "pipeline_config_id": "ma_dual_v1",   # Pipeline 配置 ID
      "strategy_id": "prob_position",       # Strategy 名称
      "pipeline_name": "ma_dual",           # 人类可读的 Pipeline 名称
      "time_range": {                       # 测试时间范围
        "start": "2025-12-01",
        "end": "2026-06-18"
      },
      "metrics": {                          # 回测指标
        "total_return_pct": 39.52,
        "max_drawdown_pct": -3.61,
        "trade_count": 59,
        "sharpe": 2.988
      },
      "last_evaluated": "2026-06-18T..."
    }
  }

注意：不保存 Pipeline 的实现细节，只引用 pipeline_configs.json 中的配置 ID。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from src.pipeline_registry import PIPELINE_REGISTRY


class BestComboRegistry:
    def __init__(self, path: Path = None):
        self.path = path or Path('data/best_combos.json')
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f'[BestComboRegistry] 加载失败: {e}')
        return {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self._data.get(symbol)

    def set(
        self,
        symbol: str,
        pipeline_name: str,
        strategy_id: str,
        metrics: Dict[str, Any],
        time_range: Dict[str, str],
        pipeline_config_id: str = None
    ) -> None:
        """
        保存最佳组合。

        Args:
            symbol: 股票代码
            pipeline_name: Pipeline 名称（如 ma_dual）
            strategy_id: Strategy 名称（如 prob_position）
            metrics: 回测指标字典
            time_range: {'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'}
            pipeline_config_id: 可选，Pipeline 配置 ID；默认从 registry 推导
        """
        if pipeline_config_id is None:
            pipeline_config_id = PIPELINE_REGISTRY.get_config_id(pipeline_name)

        self._data[symbol] = {
            'pipeline_config_id': pipeline_config_id,
            'pipeline_name': pipeline_name,
            'strategy_id': strategy_id,
            'time_range': time_range,
            'metrics': metrics,
            'last_evaluated': datetime.now().isoformat()
        }
        self.save()

    def update_from_analysis(
        self,
        analysis: Dict[str, Any],
        time_range: Optional[Dict[str, str]] = None
    ) -> None:
        """从 QuarterlyAnalyzer 的结果中更新最佳组合"""
        symbol = analysis['symbol']
        best = None
        best_quarter = None
        for q in reversed(analysis['quarters']):
            if q['best'] and q['best'].get('total_return_pct', -999) > -900:
                best = q['best']
                best_quarter = q['quarter']
                break

        if best:
            if time_range is None:
                time_range = {
                    'start': analysis.get('start'),
                    'end': analysis.get('end')
                }
            self.set(
                symbol=symbol,
                pipeline_name=best['pipeline'],
                strategy_id=best['strategy'],
                metrics={
                    'total_return_pct': best['total_return_pct'],
                    'max_drawdown_pct': best['max_drawdown_pct'],
                    'trade_count': best['trade_count'],
                    'sharpe': best['sharpe']
                },
                time_range=time_range,
                pipeline_config_id=best.get('pipeline_config_id')
            )

    def update_from_scan(
        self,
        symbol: str,
        pipeline_name: str,
        strategy_id: str,
        metrics: Dict[str, Any],
        time_range: Dict[str, str],
        pipeline_config_id: str = None
    ) -> None:
        """从全区间扫描结果中更新最佳组合"""
        self.set(
            symbol=symbol,
            pipeline_name=pipeline_name,
            strategy_id=strategy_id,
            metrics=metrics,
            time_range=time_range,
            pipeline_config_id=pipeline_config_id
        )

    def list_symbols(self) -> list:
        return list(self._data.keys())

    def list_all(self) -> Dict[str, Any]:
        return dict(self._data)
