#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bollinger Bands 规则模型。
"""

from typing import Dict, Any
import pandas as pd

from .base import BaseModel


class BollRuleModel(BaseModel):
    name = 'boll_rule'

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

    def fit(self, df: pd.DataFrame) -> None:
        required = ['upper', 'lower', 'mid']
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f'BollRuleModel 缺少列: {missing}')
        self.is_fitted = True

    def predict(self, row: pd.Series) -> Dict[str, Any]:
        close = row['close']
        upper = row['upper']
        lower = row['lower']
        mid = row['mid']

        if close <= lower:
            signal = 'bull'
            prob_bull = 0.8
        elif close >= upper:
            signal = 'bear'
            prob_bull = 0.2
        else:
            signal = 'neutral'
            prob_bull = 0.5

        score = (prob_bull - 0.5) * 2
        return {
            'score': score,
            'prob_bull': prob_bull,
            'signal': signal,
            'boll_upper': upper,
            'boll_lower': lower,
            'boll_mid': mid
        }
