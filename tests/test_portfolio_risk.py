import pytest

from src.portfolio.risk import (
    count_drawdown_events,
    max_drawdown_pct,
    recent_volatility,
    RiskProfile,
    RiskProfileManager,
    score_candidate,
)


def test_two_drawdown_events():
    # 峰值 100 -> 跌到 95(-5%) -> 回升到 ~100 -> 再跌到 96(-4%) -> 回升
    equity = [100, 98, 95, 97, 100, 101, 99, 96, 100, 102]
    assert count_drawdown_events(equity, threshold_pct=3.0, recovery_pct=1.0) == 2


def test_no_event_when_drawdown_above_threshold():
    # 最深回撤约 -2%，不触发 3% 阈值
    equity = [100, 99, 98.5, 99.5, 100.5, 101]
    assert count_drawdown_events(equity, threshold_pct=3.0) == 0


def test_single_event_does_not_double_count_without_recovery():
    # 跌破阈值后持续下探但未回升，应只算 1 次
    equity = [100, 96, 94, 92, 90, 88]
    assert count_drawdown_events(equity, threshold_pct=3.0) == 1


def test_max_drawdown_pct_negative():
    equity = [100, 90, 95]
    assert max_drawdown_pct(equity) == pytest.approx(-10.0)


def test_recent_volatility_zero_for_flat():
    assert recent_volatility([10, 10, 10, 10]) == 0.0


def test_risk_profile_defaults():
    profile = RiskProfile()
    assert profile.max_total_position == 0.40
    assert profile.max_single_position == 0.10
    assert profile.min_cash_ratio == 0.20
    assert profile.late_session_take_profit_pct == 2.0


def test_risk_profile_load_defaults_when_missing(tmp_path):
    mgr = RiskProfileManager(path=tmp_path / 'risk.json')
    profile = mgr.load()
    assert profile.max_total_position == 0.40


def test_risk_profile_save_and_update(tmp_path):
    mgr = RiskProfileManager(path=tmp_path / 'risk.json')
    mgr.update(max_total_position=0.50, max_single_position=0.15)
    reloaded = mgr.load()
    assert reloaded.max_total_position == 0.50
    assert reloaded.max_single_position == 0.15


def test_risk_profile_update_rejects_unknown_key(tmp_path):
    mgr = RiskProfileManager(path=tmp_path / 'risk.json')
    with pytest.raises(ValueError):
        mgr.update(nonsense=1.0)


def test_low_drawdown_outranks_higher_drawdown():
    profile = RiskProfile()
    pred = {'prob_bull': 0.62, 'signal': 'bull'}
    low_dd = score_candidate(
        {'max_drawdown_pct': -2.0, 'drawdown_events': 1, 'recent_volatility': 0.01},
        pred, profile)
    high_dd = score_candidate(
        {'max_drawdown_pct': -4.8, 'drawdown_events': 3, 'recent_volatility': 0.04},
        pred, profile)
    assert low_dd['final_rank'] > high_dd['final_rank']
    assert low_dd['risk_score'] < high_dd['risk_score']
