#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MACD 规则模型。
"""

from typing import Dict, Any
import pandas as pd

from .base import BaseModel


class MacdRuleModel(BaseModel):
    name = 'macd_rule'

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

    def fit(self, df: pd.DataFrame) -> None:
        # 规则模型无需训练，只需确保列存在
        required = ['dif', 'dea', 'hist']
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f'MacdRuleModel 缺少列: {missing}')
        self.is_fitted = True

    def predict(self, row: pd.Series) -> Dict[str, Any]:
        dif = row['dif']
        dea = row['dea']
        hist = row['hist']

        if dif > dea:
            signal = 'bull'
            prob_bull = 0.5 + min(0.5, abs(hist) / 10)
        elif dif < dea:
            signal = 'bear'
            prob_bull = 0.5 - min(0.5, abs(hist) / 10)
        else:
            signal = 'neutral'
            prob_bull = 0.5

        score = (prob_bull - 0.5) * 2
        return {
            'score': score,
            'prob_bull': prob_bull,
            'signal': signal,
            'dif': dif,
            'dea': dea,
            'hist': hist
        }
