import numpy as np
import pandas as pd

from src.factors.definitions import rolling_tree_prob
from src.factors.target_definitions import (
    ma_direction,
    price_direction,
    return_bucket,
    volatility_breakout,
)


def _price_df(n=12):
    return pd.DataFrame({
        "close": np.arange(1, n + 1, dtype=float),
    })


def test_price_direction_keeps_unknown_future_as_nan():
    target = price_direction(_price_df(), period=3)

    assert target.iloc[:9].tolist() == [1] * 9
    assert target.tail(3).isna().all()


def test_ma_direction_keeps_unknown_future_as_nan():
    target = ma_direction(_price_df(), window=3)

    assert target.iloc[2:9].tolist() == [1] * 7
    assert target.tail(3).isna().all()


def test_return_bucket_keeps_unknown_future_as_nan():
    target = return_bucket(_price_df(), period=4, threshold=0.0)

    assert target.iloc[:8].tolist() == [1] * 8
    assert target.tail(4).isna().all()


def test_volatility_breakout_keeps_unknown_future_as_nan():
    df = pd.DataFrame({"close": [10, 11, 10, 12, 11, 13, 12, 14, 13, 15]})

    target = volatility_breakout(df, window=3, period=2, threshold=0.5)

    assert target.tail(2).isna().all()


def test_rolling_tree_prob_excludes_rows_with_unknown_future_labels(monkeypatch):
    fit_lengths = []

    class SpyDecisionTree:
        def __init__(self, max_depth=None, random_state=None):
            pass

        def fit(self, X, y):
            fit_lengths.append(len(y))
            return self

        def predict_proba(self, X):
            return np.array([[0.25, 0.75]])

    import sklearn.tree

    monkeypatch.setattr(sklearn.tree, "DecisionTreeClassifier", SpyDecisionTree)
    df = pd.DataFrame({
        "close": np.arange(1, 10, dtype=float),
        "feature": np.arange(1, 10, dtype=float),
    })

    probs = rolling_tree_prob(
        df,
        feature_cols=["feature"],
        target_period=2,
        train_window=6,
        max_depth=3,
        min_train_samples=4,
    )

    assert fit_lengths[-1] == 5
    assert probs.iloc[-1] == 0.75
