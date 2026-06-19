from datetime import date

import pandas as pd

from src.registry_base import SimpleRegistry
from src.strategy_registry import STRATEGY_REGISTRY
from src.portfolio.risk import RiskProfile
from src.portfolio.backtester import PortfolioBacktester
from src.portfolio.walkforward import ComboChoice


class _StubPipe:
    """记录被实例化时的组合名，并据 prob 列预测。"""
    name = 'stub'

    def __init__(self):
        self._df = None

    def fit(self, df, end_idx=None):
        self._df = df

    def predict(self, idx=None):
        prob = float(self._df['prob'].iloc[-1]) if 'prob' in self._df.columns else 0.8
        return {'prob_bull': prob, 'signal': 'bull' if prob > 0.5 else 'neutral', 'score': 0.0}


def _make_df(n=80, start_price=50.0):
    dates = pd.date_range('2026-01-01', periods=n, freq='D').date
    closes = [start_price + i * 0.1 for i in range(n)]
    return pd.DataFrame({
        'date': dates, 'open': closes, 'high': [c * 1.01 for c in closes],
        'low': [c * 0.99 for c in closes], 'close': closes,
        'volume': [1_000_000] * n, 'prob': [0.8] * n,
    })


def _registries():
    # 两个不同名的桩 pipeline，便于断言 walk-forward 切换
    pipe_reg = SimpleRegistry()
    pipe_reg.register(_StubPipe, key='ma_dual')
    pipe_reg.register(_StubPipe, key='rsi')
    return pipe_reg


class _FakeBestCombo:
    def get(self, symbol):
        return None


def test_no_t_plus_1_violation_daily():
    """日线级：同一标的同一天不得既买又卖（T+1 天然满足）。"""
    dfs = {'A': _make_df(), 'B': _make_df(start_price=30.0)}
    bt = PortfolioBacktester(
        symbols=['A', 'B'], initial_capital=100000.0,
        risk_profile=RiskProfile(single_drawdown_limit_pct=90.0, max_drawdown_events=99),
        best_combo_registry=_FakeBestCombo(), pipeline_registry=_registries(),
        strategy_registry=STRATEGY_REGISTRY, load_stock=lambda s: dfs[s].copy(),
        default_pipeline='ma_dual', default_strategy='prob_position', min_history=30,
    )
    res = bt.run(start_date='2026-02-01', end_date='2026-03-20')
    by_day_sym = {}
    for t in res['trades']:
        by_day_sym.setdefault((t['date'], t['symbol']), set()).add(t['action'])
    assert all(len(v) == 1 for v in by_day_sym.values()), '存在同日买卖（T+1 违规）'


def test_walk_forward_plan_switches_combo():
    """回测应按 combo_plan 在再平衡点切换组合。"""
    dfs = {'A': _make_df()}
    plan = {'A': [
        ComboChoice(date(2026, 2, 1), 'ma_dual', 'prob_position'),
        ComboChoice(date(2026, 3, 1), 'rsi', 'prob_position'),
    ]}
    bt = PortfolioBacktester(
        symbols=['A'], initial_capital=100000.0,
        risk_profile=RiskProfile(single_drawdown_limit_pct=90.0, max_drawdown_events=99),
        best_combo_registry=_FakeBestCombo(), pipeline_registry=_registries(),
        strategy_registry=STRATEGY_REGISTRY, load_stock=lambda s: dfs[s].copy(),
        default_pipeline='ma_dual', default_strategy='prob_position', min_history=30,
        combo_plan=plan,
    )
    # 2 月用 ma_dual
    assert bt._resolve_combo('A', on_date=date(2026, 2, 15)) == ('ma_dual', 'prob_position')
    # 3 月切到 rsi
    assert bt._resolve_combo('A', on_date=date(2026, 3, 15)) == ('rsi', 'prob_position')
    res = bt.run(start_date='2026-02-05', end_date='2026-03-19')
    assert res['metrics']['walk_forward'] is True
