import pandas as pd
import pytest

from src.registry_base import SimpleRegistry
from src.strategy_registry import STRATEGY_REGISTRY
from src.portfolio.state import PortfolioStateManager
from src.portfolio.risk import RiskProfileManager
from src.portfolio.decision_engine import PortfolioDecisionEngine
from src.portfolio.schema import DecisionMode


# ---- 测试替身 -------------------------------------------------

class StubPipeline:
    """从数据帧的 prob 列读取上涨概率的桩 pipeline。"""
    name = 'ma_dual'

    def __init__(self):
        self._df = None

    def fit(self, df, end_idx=None):
        self._df = df

    def predict(self, idx=None):
        prob = float(self._df['prob'].iloc[-1]) if 'prob' in self._df.columns else 0.8
        signal = 'bull' if prob > 0.5 else ('bear' if prob < 0.4 else 'neutral')
        return {'prob_bull': prob, 'signal': signal, 'score': (prob - 0.5) * 2}


def _make_df(close_path, prob=0.85, volume=1_000_000):
    n = len(close_path)
    dates = pd.date_range('2026-01-01', periods=n, freq='D').date
    return pd.DataFrame({
        'date': dates,
        'open': close_path,
        'high': [c * 1.01 for c in close_path],
        'low': [c * 0.99 for c in close_path],
        'close': close_path,
        'volume': [volume] * n,
        'prob': [prob] * n,
    })


def _gentle_up(n=60, start=50.0):
    return [start + i * 0.1 for i in range(n)]


def _deep_drawdown(n=60, start=50.0):
    # 先涨到 70，再暴跌到 45（>30% 回撤），再缓慢回升
    path = []
    for i in range(n):
        if i < 20:
            path.append(start + i)            # 50 -> 69
        elif i < 30:
            path.append(70 - (i - 19) * 2.5)  # 70 -> 45 暴跌
        else:
            path.append(45 + (i - 30) * 0.3)
    return path


def _engine(tmp_path, dfs, *, cash=100000.0, positions=None, profile_kwargs=None):
    pipeline_registry = SimpleRegistry()
    pipeline_registry.register(StubPipeline, key='ma_dual')

    state_mgr = PortfolioStateManager(
        path=tmp_path / 'state.json', allow_unregistered=True)
    state_mgr.set_cash(cash)
    for sym, (shares, avg) in (positions or {}).items():
        state_mgr.set_position(sym, shares, avg_cost=avg)

    risk_mgr = RiskProfileManager(path=tmp_path / 'risk.json')
    if profile_kwargs:
        risk_mgr.update(**profile_kwargs)

    class FakeBestCombo:
        def get(self, symbol):
            return None

    def load_stock(symbol):
        return dfs[symbol].copy()

    return PortfolioDecisionEngine(
        state_manager=state_mgr,
        risk_manager=risk_mgr,
        best_combo_registry=FakeBestCombo(),
        pipeline_registry=pipeline_registry,
        strategy_registry=STRATEGY_REGISTRY,
        load_stock=load_stock,
        default_pipeline='ma_dual',
        default_strategy='prob_position',
    )


# ---- 测试 -----------------------------------------------------

def test_all_symbols_evaluated_with_stub_pipeline(tmp_path):
    dfs = {
        'A': _make_df(_gentle_up()),
        'B': _make_df(_gentle_up(start=30.0)),
    }
    engine = _engine(tmp_path, dfs)
    result = engine.decide(DecisionMode.CLOSE_AFTER_MARKET, symbols=['A', 'B'])
    assert len(result['candidates']) == 2
    assert all(c['selected'] for c in result['candidates'])


def test_holdings_and_cash_affect_trades(tmp_path):
    # 持有远超单股上限的仓位，应触发卖出
    dfs = {'A': _make_df(_gentle_up(start=60.0))}
    # 让最新收盘价约为 60+59*0.1≈65.9
    engine = _engine(tmp_path, dfs, cash=100000.0, positions={'A': (800, 60.0)})
    result = engine.decide(DecisionMode.CLOSE_AFTER_MARKET, symbols=['A'])
    actions = [o['action'] for o in result['orders']]
    assert 'sell' in actions


def test_single_symbol_cap_enforced(tmp_path):
    dfs = {'A': _make_df(_gentle_up())}
    engine = _engine(tmp_path, dfs, profile_kwargs={'max_single_position': 0.10})
    result = engine.decide(DecisionMode.CLOSE_AFTER_MARKET, symbols=['A'])
    equity = result['portfolio']['estimated_equity']
    buys = [o for o in result['orders'] if o['action'] == 'buy']
    assert buys, 'expected a buy order'
    bought_value = sum(o['shares'] * o['price'] for o in buys)
    one_lot_value = buys[0]['price'] * 100
    assert bought_value <= 0.10 * equity + one_lot_value  # 容一手取整


def test_total_exposure_cap_enforced(tmp_path):
    syms = [chr(ord('A') + i) for i in range(8)]
    dfs = {s: _make_df(_gentle_up(start=20.0 + i)) for i, s in enumerate(syms)}
    engine = _engine(tmp_path, dfs, profile_kwargs={
        'max_total_position': 0.40, 'max_single_position': 0.10})
    result = engine.decide(DecisionMode.CLOSE_AFTER_MARKET, symbols=syms)
    equity = result['portfolio']['estimated_equity']
    bought_value = sum(o['shares'] * o['price'] for o in result['orders'] if o['action'] == 'buy')
    assert bought_value <= 0.40 * equity + 1e-6 + 5000  # 容订单离散化误差
    assert result['portfolio']['target_stock_exposure'] <= 0.42


def test_lot_size_rounds_orders(tmp_path):
    dfs = {'A': _make_df(_gentle_up(start=33.33))}
    engine = _engine(tmp_path, dfs)
    result = engine.decide(DecisionMode.CLOSE_AFTER_MARKET, symbols=['A'])
    for o in result['orders']:
        assert o['shares'] % 100 == 0


def test_low_drawdown_beats_higher_drawdown(tmp_path):
    # 两只都有强烈看多信号，但一只历史回撤巨大；收紧总仓位使二者不能同时买满。
    dfs = {
        'LOWDD': _make_df(_gentle_up(start=50.0), prob=0.85),
        'HIGHDD': _make_df(_deep_drawdown(), prob=0.85),
    }
    engine = _engine(tmp_path, dfs, profile_kwargs={
        'max_total_position': 0.10, 'max_single_position': 0.10,
        'single_drawdown_limit_pct': 60.0})  # 放宽硬限使 HIGHDD 不被直接拒绝
    result = engine.decide(DecisionMode.CLOSE_AFTER_MARKET, symbols=['LOWDD', 'HIGHDD'])
    ranks = {c['symbol']: c['rank'] for c in result['candidates']}
    assert ranks['LOWDD'] < ranks['HIGHDD']  # 低回撤排名更靠前
    buys = [o['symbol'] for o in result['orders'] if o['action'] == 'buy']
    assert 'LOWDD' in buys


def test_late_session_plan_generated(tmp_path):
    from datetime import datetime, timezone, timedelta
    cst = timezone(timedelta(hours=8))
    dfs = {'A': _make_df(_gentle_up(start=60.0))}
    engine = _engine(tmp_path, dfs, profile_kwargs={'late_session_take_profit_pct': 2.0})
    ts = datetime.now(cst).replace(microsecond=0).isoformat()
    quotes = {
        'A': {
            'timestamp': ts, 'price': 66.0, 'open': 65.0,
            'high': 67.0, 'low': 64.5, 'prev_close': 65.5, 'volume': 1_000_000,
        }
    }
    result = engine.decide(DecisionMode.LATE_SESSION, symbols=['A'], quotes=quotes)
    if any(o['action'] == 'buy' for o in result['orders']):
        assert result['late_session_plan']
        plan = result['late_session_plan'][0]
        assert plan['take_profit_price'] == pytest.approx(plan['entry_price'] * 1.02, rel=1e-6)
