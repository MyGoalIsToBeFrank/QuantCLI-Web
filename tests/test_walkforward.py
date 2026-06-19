from datetime import date

import pandas as pd
import pytest

from src.portfolio.walkforward import (
    WalkForwardSelector, ComboChoice, combo_for_date, DEFAULT_CANDIDATES,
)


def test_select_uses_only_pre_cutoff_data():
    """无前视：select_at 的训练窗口必须严格早于 cutoff。"""
    seen = []

    def scorer(symbol, pl, st, start, end):
        seen.append((start, end))
        return {'sharpe': 1.0, 'total_return_pct': 5.0, 'max_drawdown_pct': -2.0,
                'trade_count': 10}

    sel = WalkForwardSelector(candidate_combos=[('ma_dual', 'low_risk')], scorer=scorer)
    cutoff = date(2026, 4, 1)
    sel.select_at('002156.SZ', cutoff)

    assert seen, '应至少评估一个组合'
    for start, end in seen:
        assert end < cutoff, f'训练窗口 end={end} 不得 >= cutoff={cutoff}'
        assert start < cutoff


def test_select_picks_best_by_metric():
    scores = {
        ('ma_dual', 'low_risk'): 0.5,
        ('rsi', 'low_risk'): 2.0,   # 最佳
        ('macd', 'low_risk'): 1.0,
    }

    def scorer(symbol, pl, st, start, end):
        return {'sharpe': scores[(pl, st)], 'trade_count': 10}

    sel = WalkForwardSelector(candidate_combos=list(scores.keys()),
                              metric='sharpe', scorer=scorer)
    ch = sel.select_at('X', date(2026, 4, 1))
    assert (ch.pipeline, ch.strategy) == ('rsi', 'low_risk')


def test_select_skips_combos_below_min_trades():
    def scorer(symbol, pl, st, start, end):
        # 高 sharpe 但交易过少，应被跳过
        if pl == 'ma_dual':
            return {'sharpe': 9.0, 'trade_count': 1}
        return {'sharpe': 1.0, 'trade_count': 20}

    sel = WalkForwardSelector(
        candidate_combos=[('ma_dual', 'low_risk'), ('rsi', 'low_risk')],
        min_trades=3, scorer=scorer)
    ch = sel.select_at('X', date(2026, 4, 1))
    assert ch.pipeline == 'rsi'


def test_rebalance_dates_step():
    sel = WalkForwardSelector(step_days=30)
    dates = sel.rebalance_dates('2026-01-01', '2026-03-15')
    assert dates[0] == date(2026, 1, 1)
    assert all((dates[i + 1] - dates[i]).days == 30 for i in range(len(dates) - 1))
    assert dates[-1] <= date(2026, 3, 15)


def test_combo_for_date_lookup():
    choices = [
        ComboChoice(date(2026, 1, 1), 'ma_dual', 'low_risk'),
        ComboChoice(date(2026, 4, 1), 'rsi', 'low_risk'),
    ]
    assert combo_for_date(choices, date(2026, 2, 1)).pipeline == 'ma_dual'
    assert combo_for_date(choices, date(2026, 5, 1)).pipeline == 'rsi'
    assert combo_for_date(choices, date(2025, 12, 1)) is None


def test_build_plan_per_symbol():
    def scorer(symbol, pl, st, start, end):
        return {'sharpe': 1.0 if pl == 'rsi' else 0.1, 'trade_count': 10}

    sel = WalkForwardSelector(
        candidate_combos=[('ma_dual', 'low_risk'), ('rsi', 'low_risk')],
        step_days=63, scorer=scorer)
    plan = sel.build_plan(['A', 'B'], '2026-01-01', '2026-06-01')
    assert set(plan.keys()) == {'A', 'B'}
    assert all(ch.pipeline == 'rsi' for ch in plan['A'])
    # 计划按时间递增
    fa = [ch.effective_from for ch in plan['A']]
    assert fa == sorted(fa)
