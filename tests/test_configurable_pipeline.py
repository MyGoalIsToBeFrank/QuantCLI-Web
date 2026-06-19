import pandas as pd

from src.pipelines.configurable import ConfigurablePipeline


def _ohlcv(n=150):
    dates = pd.date_range("2026-01-01", periods=n, freq="D").date
    close = [float(i + 1) for i in range(n)]
    return pd.DataFrame({
        "date": dates,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": [1000] * n,
    })


def test_predict_uses_latest_feature_row_not_last_known_target_row(monkeypatch):
    seen = {}

    class DummyModel:
        def __init__(self, config):
            self.config = config

        def fit(self, df):
            seen["train_last_date"] = df["date"].iloc[-1]

        def predict(self, row):
            seen["predict_date"] = row["date"]
            return {"prob_bull": 0.5, "score": 0.0, "signal": "neutral"}

    from src.pipelines import configurable

    monkeypatch.setattr(configurable.MODEL_REGISTRY, "create", lambda *args, **kwargs: DummyModel(args[1]))

    pipeline = ConfigurablePipeline("ma_dual_v1")
    raw = _ohlcv()
    pipeline.fit(raw)
    pipeline.predict()

    assert seen["train_last_date"] < raw["date"].iloc[-1]
    assert seen["predict_date"] == raw["date"].iloc[-1]
