#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双随机森林模型：分别预测 MA5 / MA20 方向，加权综合。
"""

from typing import Dict, Any
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from .base import BaseModel


class DualRandomForestModel(BaseModel):
    name = 'dual_random_forest'

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model_ma5 = None
        self.model_ma20 = None

    def fit(self, df: pd.DataFrame) -> None:
        feature_cols = self.config['feature_cols']
        X = df[feature_cols].values
        y_ma5 = df['target_ma5'].values
        y_ma20 = df['target_ma20'].values

        params = self.model_params()
        max_depth = params.get('max_depth', 3)
        n_estimators = params.get('n_estimators', 30)

        self.model_ma5 = RandomForestClassifier(
            n_estimators=n_estimators, max_depth=max_depth,
            random_state=42, class_weight='balanced'
        )
        self.model_ma5.fit(X, y_ma5)

        self.model_ma20 = RandomForestClassifier(
            n_estimators=n_estimators, max_depth=max_depth,
            random_state=42, class_weight='balanced'
        )
        self.model_ma20.fit(X, y_ma20)
        self.is_fitted = True

    def predict(self, row: pd.Series) -> Dict[str, Any]:
        feature_cols = self.config['feature_cols']
        X = row[feature_cols].values.reshape(1, -1)
        params = self.model_params()
        w_ma5 = params.get('w_ma5', 0.6)
        w_ma20 = params.get('w_ma20', 0.4)

        prob_ma5 = self.model_ma5.predict_proba(X)[0][1]
        prob_ma20 = self.model_ma20.predict_proba(X)[0][1]
        prob_combined = w_ma5 * prob_ma5 + w_ma20 * prob_ma20

        score = max(-1.0, min(1.0, (prob_combined - 0.5) * 2))

        if prob_combined > 0.65:
            signal = 'bull'
        elif prob_combined < 0.35:
            signal = 'bear'
        else:
            signal = 'neutral'

        return {
            'score': score,
            'prob_bull': prob_combined,
            'signal': signal,
            'prob_ma5': prob_ma5,
            'prob_ma20': prob_ma20
        }
