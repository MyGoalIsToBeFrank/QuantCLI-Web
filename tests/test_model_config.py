import pandas as pd

from src.models.dual_logistic import DualLogisticModel
from src.models.dual_random_forest import DualRandomForestModel


def _training_df():
    return pd.DataFrame({
        "f1": [0, 1, 2, 3, 4, 5, 6, 7],
        "f2": [7, 6, 5, 4, 3, 2, 1, 0],
        "target_ma5": [0, 1, 0, 1, 0, 1, 0, 1],
        "target_ma20": [1, 0, 1, 0, 1, 0, 1, 0],
    })


def test_dual_random_forest_reads_model_params():
    model = DualRandomForestModel({
        "feature_cols": ["f1", "f2"],
        "model_params": {
            "n_estimators": 7,
            "max_depth": 2,
        },
    })

    model.fit(_training_df())

    assert model.model_ma5.n_estimators == 7
    assert model.model_ma5.max_depth == 2
    assert model.model_ma20.n_estimators == 7
    assert model.model_ma20.max_depth == 2


def test_dual_logistic_predict_reads_weight_model_params():
    class DummyEstimator:
        def __init__(self, positive_prob):
            self.positive_prob = positive_prob

        def predict_proba(self, X):
            return [[1 - self.positive_prob, self.positive_prob]]

    model = DualLogisticModel({
        "feature_cols": ["f1", "f2"],
        "model_params": {
            "w_ma5": 0.2,
            "w_ma20": 0.8,
        },
    })
    model.model_ma5 = DummyEstimator(0.9)
    model.model_ma20 = DummyEstimator(0.2)

    pred = model.predict(pd.Series({"f1": 1.0, "f2": 2.0}))

    assert abs(pred["prob_bull"] - 0.34) < 1e-12
