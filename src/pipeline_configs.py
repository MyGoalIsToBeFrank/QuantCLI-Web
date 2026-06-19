#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PipelineConfigManager：管线配置管理

每个 Pipeline 的完整配置单独存储在 data/pipeline_configs.json，包含：
  - 因子列表（引用 FactorRegistry）
  - 模型类型与超参数
  - 训练目标（target）
  - 预测输出格式
  - 人类可读说明

Pipeline 类通过 config_id 加载配置，无需硬编码因子计算逻辑。
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from copy import deepcopy


DEFAULT_PIPELINE_CONFIGS = {
    'rf_ma_dual_v1': {
        'name': '正则化双随机森林 MA 预测',
        'description': '与 ma_dual 相同的特征与目标，但用两颗 max_depth=3 的随机森林分别预测 MA5/MA20 方向',
        'version': '1.0',
        'factors': [
            {'name': 'sma', 'params': {'window': 5}, 'output_col': 'ma5'},
            {'name': 'sma', 'params': {'window': 10}, 'output_col': 'ma10'},
            {'name': 'sma', 'params': {'window': 20}, 'output_col': 'ma20'},
            {'name': 'sma', 'params': {'window': 60}, 'output_col': 'ma60'},
            {'name': 'std', 'params': {'window': 20}, 'output_col': 'std20'},
            {'name': 'std', 'params': {'window': 60}, 'output_col': 'std60'},
            {'name': 'zscore', 'params': {'window': 20}, 'output_col': 'z20'},
            {'name': 'zscore', 'params': {'window': 60}, 'output_col': 'z60'},
            {'name': 'slope', 'params': {'window': 20, 'period': 5}, 'output_col': 'ma20_slope5'},
            {'name': 'slope', 'params': {'window': 20, 'period': 10}, 'output_col': 'ma20_slope10'},
            {'name': 'slope', 'params': {'window': 60, 'period': 5}, 'output_col': 'ma60_slope5'},
            {'name': 'slope', 'params': {'window': 60, 'period': 10}, 'output_col': 'ma60_slope10'},
            {'name': 'returns', 'params': {'period': 5}, 'output_col': 'ret5'},
            {'name': 'returns', 'params': {'period': 10}, 'output_col': 'ret10'},
            {'name': 'returns', 'params': {'period': 20}, 'output_col': 'ret20'},
            {'name': 'golden_cross', 'params': {'fast': 20, 'slow': 60}, 'output_col': 'golden_cross'},
            {'name': 'ma_gap', 'params': {'fast': 20, 'slow': 60}, 'output_col': 'ma20_ma60_gap'},
            {'name': 'volatility_ratio', 'params': {'window': 20}, 'output_col': 'vol20'}
        ],
        'model': {
            'type': 'dual_random_forest',
            'params': {'w_ma5': 0.6, 'w_ma20': 0.4, 'max_depth': 3, 'n_estimators': 30}
        },
        'targets': [
            {'name': 'ma_direction', 'params': {'window': 5}, 'output_col': 'target_ma5'},
            {'name': 'ma_direction', 'params': {'window': 20}, 'output_col': 'target_ma20'}
        ],
        'feature_cols': [
            'ma20', 'ma60', 'z20', 'z60',
            'ma20_slope5', 'ma20_slope10', 'ma60_slope5', 'ma60_slope10',
            'ret5', 'ret10', 'ret20',
            'golden_cross', 'ma20_ma60_gap', 'vol20'
        ],
        'predictions': {
            'prob_bull': 'prob_combined',
            'score': 'score',
            'signal': 'signal',
            'prob_ma5': 'prob_ma5',
            'prob_ma20': 'prob_ma20'
        }
    },
    'dt_logistic_v1': {
        'name': 'DT + Logistic 滚动预测',
        'description': '用滚动窗口决策树提取 dt_prob 特征，再用逻辑回归综合预测未来5日方向',
        'version': '1.0',
        'factors': [
            {'name': 'sma', 'params': {'window': 20}, 'output_col': 'ma20'},
            {'name': 'sma', 'params': {'window': 60}, 'output_col': 'ma60'},
            {'name': 'zscore', 'params': {'window': 20}, 'output_col': 'z20'},
            {'name': 'returns', 'params': {'period': 5}, 'output_col': 'ret5'},
            {'name': 'returns', 'params': {'period': 20}, 'output_col': 'ret20'},
            {'name': 'volatility_ratio', 'params': {'window': 20}, 'output_col': 'vol20'},
            {'name': 'rolling_tree_prob', 'params': {
                'feature_cols': ['ma20', 'z20', 'ret5', 'ret20', 'vol20'],
                'target_period': 5,
                'train_window': 126,
                'max_depth': 5
            }, 'output_col': 'dt_prob'}
        ],
        'model': {
            'type': 'logistic',
            'params': {}
        },
        'targets': [
            {'name': 'price_direction', 'params': {'period': 5}, 'output_col': 'target_up5'}
        ],
        'feature_cols': ['ma20', 'ma60', 'z20', 'ret5', 'ret20', 'vol20', 'dt_prob'],
        'predictions': {
            'prob_bull': 'prob_bull',
            'score': 'score',
            'signal': 'signal'
        }
    },
    'ma_dual_v1': {
        'name': 'MA 双模型 Logistic',
        'description': '基于单股票 MA5/MA20 方向的 LogisticRegression 双模型，加权综合概率',
        'version': '1.0',
        'factors': [
            {'name': 'sma', 'params': {'window': 5}, 'output_col': 'ma5'},
            {'name': 'sma', 'params': {'window': 10}, 'output_col': 'ma10'},
            {'name': 'sma', 'params': {'window': 20}, 'output_col': 'ma20'},
            {'name': 'sma', 'params': {'window': 60}, 'output_col': 'ma60'},
            {'name': 'std', 'params': {'window': 20}, 'output_col': 'std20'},
            {'name': 'std', 'params': {'window': 60}, 'output_col': 'std60'},
            {'name': 'zscore', 'params': {'window': 20}, 'output_col': 'z20'},
            {'name': 'zscore', 'params': {'window': 60}, 'output_col': 'z60'},
            {'name': 'slope', 'params': {'window': 20, 'period': 5}, 'output_col': 'ma20_slope5'},
            {'name': 'slope', 'params': {'window': 20, 'period': 10}, 'output_col': 'ma20_slope10'},
            {'name': 'slope', 'params': {'window': 60, 'period': 5}, 'output_col': 'ma60_slope5'},
            {'name': 'slope', 'params': {'window': 60, 'period': 10}, 'output_col': 'ma60_slope10'},
            {'name': 'returns', 'params': {'period': 5}, 'output_col': 'ret5'},
            {'name': 'returns', 'params': {'period': 10}, 'output_col': 'ret10'},
            {'name': 'returns', 'params': {'period': 20}, 'output_col': 'ret20'},
            {'name': 'golden_cross', 'params': {'fast': 20, 'slow': 60}, 'output_col': 'golden_cross'},
            {'name': 'ma_gap', 'params': {'fast': 20, 'slow': 60}, 'output_col': 'ma20_ma60_gap'},
            {'name': 'volatility_ratio', 'params': {'window': 20}, 'output_col': 'vol20'}
        ],
        'model': {
            'type': 'dual_logistic',
            'params': {'w_ma5': 0.6, 'w_ma20': 0.4}
        },
        'targets': [
            {'name': 'ma_direction', 'params': {'window': 5}, 'output_col': 'target_ma5'},
            {'name': 'ma_direction', 'params': {'window': 20}, 'output_col': 'target_ma20'}
        ],
        'feature_cols': [
            'ma20', 'ma60', 'z20', 'z60',
            'ma20_slope5', 'ma20_slope10', 'ma60_slope5', 'ma60_slope10',
            'ret5', 'ret10', 'ret20',
            'golden_cross', 'ma20_ma60_gap', 'vol20'
        ],
        'predictions': {
            'prob_bull': 'prob_combined',
            'score': 'score',
            'signal': 'signal',
            'prob_ma5': 'prob_ma5',
            'prob_ma20': 'prob_ma20'
        }
    },
    'macd_v1': {
        'name': 'MACD 动量',
        'description': '基于 MACD dif/dea/hist 的动量信号',
        'version': '1.0',
        'factors': [
            {'name': 'macd', 'params': {'fast': 12, 'slow': 26, 'signal': 9}, 'output_col': 'macd'}
        ],
        'model': {
            'type': 'macd_rule',
            'params': {}
        },
        'feature_cols': ['dif', 'dea', 'hist'],
        'predictions': {
            'prob_bull': 'prob_bull',
            'score': 'score',
            'signal': 'signal',
            'dif': 'dif',
            'dea': 'dea',
            'hist': 'hist'
        }
    },
    'rsi_v1': {
        'name': 'RSI 阈值',
        'description': '基于 RSI 超买超卖的反转信号',
        'version': '1.0',
        'factors': [
            {'name': 'rsi', 'params': {'window': 14}, 'output_col': 'rsi'}
        ],
        'model': {
            'type': 'rsi_rule',
            'params': {'oversold': 30, 'overbought': 70}
        },
        'feature_cols': ['rsi'],
        'predictions': {
            'prob_bull': 'prob_bull',
            'score': 'score',
            'signal': 'signal',
            'rsi': 'rsi'
        }
    },
    'boll_v1': {
        'name': '布林带反转',
        'description': '基于布林带上下轨的均值回归信号',
        'version': '1.0',
        'factors': [
            {'name': 'bollinger', 'params': {'window': 20, 'std_dev': 2}, 'output_col': 'boll'}
        ],
        'model': {
            'type': 'boll_rule',
            'params': {}
        },
        'feature_cols': ['upper', 'lower', 'mid'],
        'predictions': {
            'prob_bull': 'prob_bull',
            'score': 'score',
            'signal': 'signal',
            'boll_upper': 'upper',
            'boll_lower': 'lower',
            'boll_mid': 'mid'
        }
    }
}


class PipelineConfigManager:
    def __init__(self, path: Path = None):
        self.path = path or Path('data/pipeline_configs.json')
        self._configs = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                # 用默认值补充缺失键
                for key, default in DEFAULT_PIPELINE_CONFIGS.items():
                    if key not in loaded:
                        loaded[key] = deepcopy(default)
                return loaded
            except Exception as e:
                print(f'[PipelineConfigManager] 加载失败: {e}')
        return deepcopy(DEFAULT_PIPELINE_CONFIGS)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self._configs, f, ensure_ascii=False, indent=2)

    def get(self, config_id: str) -> Dict[str, Any]:
        if config_id not in self._configs:
            raise KeyError(f'未注册的 Pipeline 配置: {config_id}')
        return deepcopy(self._configs[config_id])

    def set(self, config_id: str, config: Dict[str, Any]) -> None:
        self._configs[config_id] = deepcopy(config)
        self.save()

    def list(self) -> Dict[str, Dict[str, Any]]:
        return deepcopy(self._configs)

    def reset_to_defaults(self) -> None:
        self._configs = deepcopy(DEFAULT_PIPELINE_CONFIGS)
        self.save()


# 全局实例
PIPELINE_CONFIG_MANAGER = PipelineConfigManager()
