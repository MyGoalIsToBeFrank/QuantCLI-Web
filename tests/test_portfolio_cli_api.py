import argparse
import json

import pytest

from src.cli.commands import portfolio_cmd
from src.portfolio.state import PortfolioStateManager
from src.portfolio.risk import RiskProfileManager


def _parser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command')
    portfolio_cmd.register(sub)
    return parser


def _patch_managers(monkeypatch, tmp_path):
    state_path = tmp_path / 'state.json'
    risk_path = tmp_path / 'risk.json'
    monkeypatch.setattr(portfolio_cmd, 'PortfolioStateManager',
                        lambda: PortfolioStateManager(path=state_path))
    monkeypatch.setattr(portfolio_cmd, 'RiskProfileManager',
                        lambda: RiskProfileManager(path=risk_path))
    return state_path, risk_path


# ---- CLI ------------------------------------------------------

def test_portfolio_command_registered():
    parser = _parser()
    args = parser.parse_args(['portfolio', 'show'])
    assert hasattr(args, 'func')


def test_cli_show(monkeypatch, tmp_path, capsys):
    _patch_managers(monkeypatch, tmp_path)
    parser = _parser()
    args = parser.parse_args(['portfolio', 'show'])
    args.func(args)
    out = capsys.readouterr().out
    assert '组合账户状态' in out


def test_cli_set_cash(monkeypatch, tmp_path, capsys):
    state_path, _ = _patch_managers(monkeypatch, tmp_path)
    parser = _parser()
    args = parser.parse_args(['portfolio', 'set-cash', '88888'])
    args.func(args)
    assert PortfolioStateManager(path=state_path).load().cash == 88888.0


def test_cli_set_position(monkeypatch, tmp_path):
    state_path, _ = _patch_managers(monkeypatch, tmp_path)
    parser = _parser()
    args = parser.parse_args(
        ['portfolio', 'set-position', '002156.SZ', '800', '--avg-cost', '62.5'])
    args.func(args)
    pos = PortfolioStateManager(path=state_path).load().positions['002156.SZ']
    assert pos.shares == 800
    assert pos.avg_cost == 62.5


def test_cli_risk_set(monkeypatch, tmp_path):
    _, risk_path = _patch_managers(monkeypatch, tmp_path)
    parser = _parser()
    args = parser.parse_args(
        ['portfolio', 'risk-profile', 'set', '--max-total-position', '0.5'])
    args.func(args)
    assert RiskProfileManager(path=risk_path).load().max_total_position == 0.5


def test_cli_decide_close_mode(monkeypatch, tmp_path, capsys):
    _patch_managers(monkeypatch, tmp_path)

    class StubEngine:
        def __init__(self, *a, **k):
            pass

        def decide(self, mode, symbols=None, quotes=None, open_prices=None):
            return {
                'mode': mode,
                'timestamp': '2026-06-19T15:00:00+08:00',
                'portfolio': {
                    'cash': 100000.0, 'estimated_equity': 100000.0,
                    'current_stock_exposure': 0.0, 'target_stock_exposure': 0.1,
                    'cash_after_trades': 90000.0, 'lot_size': 100,
                },
                'risk_profile': {},
                'orders': [],
                'candidates': [],
                'late_session_plan': [],
            }

    monkeypatch.setattr(portfolio_cmd, 'PortfolioDecisionEngine', StubEngine)
    parser = _parser()
    args = parser.parse_args(['portfolio', 'decide', '--mode', 'close_after_market'])
    args.func(args)
    out = capsys.readouterr().out
    assert '组合决策' in out
    assert '订单建议' in out


# ---- API ------------------------------------------------------

@pytest.fixture
def client(monkeypatch, tmp_path):
    import src.api_server as api

    monkeypatch.setattr(api, 'PortfolioStateManager',
                        lambda: PortfolioStateManager(path=tmp_path / 'state.json'))
    monkeypatch.setattr(api, 'RiskProfileManager',
                        lambda: RiskProfileManager(path=tmp_path / 'risk.json'))
    api.app.config['TESTING'] = True
    return api.app.test_client()


def test_api_get_portfolio_state(client):
    resp = client.get('/api/portfolio_state')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['success'] is True
    assert body['state']['lot_size'] == 100


def test_api_put_portfolio_state(client):
    resp = client.put('/api/portfolio_state', json={
        'cash': 55000.0,
        'positions': {'002156.SZ': {'shares': 500, 'avg_cost': 60.0}},
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['state']['cash'] == 55000.0
    assert body['state']['positions']['002156.SZ']['shares'] == 500


def test_api_put_portfolio_state_rejects_negative_cash(client):
    resp = client.put('/api/portfolio_state', json={'cash': -1})
    assert resp.status_code == 400


def test_api_position_post_and_delete(client):
    resp = client.post('/api/portfolio_position',
                       json={'symbol': '002156.SZ', 'shares': 300, 'avg_cost': 62.0})
    assert resp.status_code == 200
    assert resp.get_json()['state']['positions']['002156.SZ']['shares'] == 300

    resp = client.delete('/api/portfolio_position', json={'symbol': '002156.SZ'})
    assert resp.status_code == 200
    assert '002156.SZ' not in resp.get_json()['state']['positions']


def test_api_risk_profile_get_put(client):
    resp = client.get('/api/portfolio_risk_profile')
    assert resp.status_code == 200
    assert resp.get_json()['risk_profile']['max_total_position'] == 0.4

    resp = client.put('/api/portfolio_risk_profile', json={'max_total_position': 0.45})
    assert resp.status_code == 200
    assert resp.get_json()['risk_profile']['max_total_position'] == 0.45


def test_api_portfolio_decide(client, monkeypatch):
    import src.api_server as api

    class StubEngine:
        def __init__(self, *a, **k):
            pass

        def decide(self, mode, symbols=None, quotes=None, open_prices=None):
            return {'mode': mode, 'orders': [], 'candidates': [],
                    'late_session_plan': [], 'portfolio': {}, 'risk_profile': {},
                    'timestamp': 'now'}

    monkeypatch.setattr(api, 'PortfolioDecisionEngine', StubEngine)
    resp = client.post('/api/portfolio_decide', json={'mode': 'close_after_market'})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['success'] is True
    assert body['result']['mode'] == 'close_after_market'


def test_api_existing_endpoints_still_work(client):
    # 回归：现有端点不受影响
    resp = client.get('/api/stocks')
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True
