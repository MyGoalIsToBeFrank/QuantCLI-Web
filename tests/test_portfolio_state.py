import json
from pathlib import Path

import pytest

from src.portfolio.state import Position, PortfolioState, PortfolioStateManager
from src.portfolio.schema import DEFAULT_LOT_SIZE, DEFAULT_CASH


def test_default_state_when_file_missing(tmp_path):
    mgr = PortfolioStateManager(path=tmp_path / 'portfolio_state.json')
    state = mgr.load()
    assert state.cash == DEFAULT_CASH
    assert state.lot_size == DEFAULT_LOT_SIZE
    assert state.positions == {}


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / 'portfolio_state.json'
    mgr = PortfolioStateManager(path=path)
    mgr.set_cash(50000.0)
    mgr.set_position('002156.SZ', 800, avg_cost=62.5, note='manual')

    # 文件确实写出，且 JSON 可读
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    assert raw['cash'] == 50000.0
    assert raw['positions']['002156.SZ']['shares'] == 800
    assert raw['lot_size'] == 100

    reloaded = mgr.load()
    assert reloaded.cash == 50000.0
    assert reloaded.positions['002156.SZ'].shares == 800
    assert reloaded.positions['002156.SZ'].avg_cost == 62.5


def test_negative_cash_rejected():
    with pytest.raises(ValueError):
        PortfolioState(cash=-1.0)


def test_negative_shares_rejected():
    with pytest.raises(ValueError):
        Position(shares=-100)


def test_non_integer_shares_rejected():
    with pytest.raises(ValueError):
        Position(shares=150.5)


def test_unregistered_symbol_rejected(tmp_path):
    mgr = PortfolioStateManager(path=tmp_path / 'portfolio_state.json')
    with pytest.raises(ValueError):
        mgr.set_position('NOPE.XX', 100)


def test_remove_position(tmp_path):
    mgr = PortfolioStateManager(path=tmp_path / 'portfolio_state.json')
    mgr.set_position('002156.SZ', 800, avg_cost=62.5)
    mgr.remove_position('002156.SZ')
    assert '002156.SZ' not in mgr.load().positions


def test_total_equity():
    state = PortfolioState(
        cash=10000.0,
        positions={'002156.SZ': Position(shares=100, avg_cost=60.0)},
    )
    equity = state.total_equity({'002156.SZ': 70.0})
    assert equity == 10000.0 + 100 * 70.0


def test_set_position_preserves_avg_cost_when_omitted(tmp_path):
    mgr = PortfolioStateManager(path=tmp_path / 'portfolio_state.json')
    mgr.set_position('002156.SZ', 800, avg_cost=62.5)
    mgr.set_position('002156.SZ', 900)  # 不传 avg_cost
    reloaded = mgr.load()
    assert reloaded.positions['002156.SZ'].shares == 900
    assert reloaded.positions['002156.SZ'].avg_cost == 62.5
