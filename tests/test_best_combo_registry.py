from src.analysis.best_combo_registry import BestComboRegistry


def test_best_combo_registry_writes_only_configured_path(tmp_path):
    path = tmp_path / "best.json"
    registry = BestComboRegistry(path=path)

    registry.set(
        symbol="002156.SZ",
        pipeline_name="ma_dual",
        strategy_id="prob_position",
        metrics={
            "total_return_pct": 1.0,
            "max_drawdown_pct": -0.5,
            "trade_count": 2,
            "sharpe": 0.3,
        },
        time_range={"start": "2026-01-01", "end": "2026-01-31"},
    )

    assert path.exists()
    assert "002156.SZ" in path.read_text(encoding="utf-8")


def test_backend_self_test_uses_temp_best_combo_registry(monkeypatch, tmp_path):
    import tests.test_backend as backend_tests

    created_paths = []

    class FakeRegistry:
        def __init__(self, path=None):
            created_paths.append(path)
            if path is None:
                raise AssertionError("test_backend must not use production best_combos.json")

        def set(self, **kwargs):
            self.combo = kwargs

        def get(self, symbol):
            return {
                "pipeline_name": "ma_dual",
                "strategy_id": "prob_position",
            }

    monkeypatch.setattr(backend_tests, "BestComboRegistry", FakeRegistry)
    monkeypatch.setattr(backend_tests, "TEST_OUTPUT_DIR", tmp_path)

    backend_tests.test_best_combo_registry()

    assert created_paths == [tmp_path / "best_combos_test.json"]
