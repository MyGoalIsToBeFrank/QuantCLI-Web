#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSI 规则模型。
"""

from typing import Dict, Any
import pandas as pd

from .base import BaseModel


class RsiRuleModel(BaseModel):
    name = 'rsi_rule'

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

    def fit(self, df: pd.DataFrame) -> None:
        if 'rsi' not in df.columns:
            raise ValueError('RsiRuleModel 缺少列: rsi')
        self.is_fitted = True

    def predict(self, row: pd.Series) -> Dict[str, Any]:
        rsi_value = row['rsi']
        params = self.model_params()
        oversold = params.get('oversold', 30)
        overbought = params.get('overbought', 70)

        if rsi_value < oversold:
            signal = 'bull'
            prob_bull = 1.0 - rsi_value / 100
        elif rsi_value > overbought:
            signal = 'bear'
            prob_bull = 1.0 - rsi_value / 100
        else:
            signal = 'neutral'
            prob_bull = 0.5

        score = (prob_bull - 0.5) * 2
        return {
            'score': score,
            'prob_bull': prob_bull,
            'signal': signal,
            'rsi': rsi_value
        }
