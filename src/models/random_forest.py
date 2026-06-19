#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单目标随机森林模型。
"""

from typing import Dict, Any
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from .base import BaseModel


class RandomForestModel(BaseModel):
    name = 'random_forest'

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model = None
        self.target_col = None

    def fit(self, df: pd.DataFrame) -> None:
        feature_cols = self.config['feature_cols']
        target_spec = self.config['targets'][0]
        self.target_col = target_spec.get('output_col') or target_spec['name']

        X = df[feature_cols].values
        y = df[self.target_col].values

        params = self.model_params()
        self.model = RandomForestClassifier(
            n_estimators=params.get('n_estimators', 100),
            max_depth=params.get('max_depth', 5),
            random_state=42,
            class_weight='balanced'
        )
        self.model.fit(X, y)
        self.is_fitted = True

    def predict(self, row: pd.Series) -> Dict[str, Any]:
        feature_cols = self.config['feature_cols']
        X = row[feature_cols].values.reshape(1, -1)
        prob_bull = self.model.predict_proba(X)[0][1]

        score = max(-1.0, min(1.0, (prob_bull - 0.5) * 2))

        if prob_bull > 0.65:
            signal = 'bull'
        elif prob_bull < 0.35:
            signal = 'bear'
        else:
            signal = 'neutral'

        return {'score': score, 'prob_bull': prob_bull, 'signal': signal}
