"""
组合账户状态：现金 + 多股持仓

`data/portfolio_state.json` 人类可编辑，加载安全。约定：
  - lot_size 默认 100，且为执行单位
  - shares 必须为非负整数
  - cash 必须非负
  - 未注册的股票被拒绝（除非未来迁移显式放开）
  - 缺失状态文件时创建默认空状态（cash=100000.0, positions={}, lot_size=100）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

from src.data.stock_registry import StockRegistry, REGISTRY
from .schema import DEFAULT_LOT_SIZE, DEFAULT_CASH, SCHEMA_VERSION

# 北京时间（A 股时区），用于 updated_at 时间戳
_CST = timezone(timedelta(hours=8))


def _now_iso() -> str:
    return datetime.now(_CST).replace(microsecond=0).isoformat()


@dataclass
class Position:
    """单只股票持仓。"""

    shares: int = 0
    avg_cost: float = 0.0
    note: str = ''

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        if int(self.shares) != self.shares or self.shares < 0:
            raise ValueError(f'持股数必须为非负整数，得到 {self.shares}')
        self.shares = int(self.shares)
        if self.avg_cost < 0:
            raise ValueError(f'平均成本必须非负，得到 {self.avg_cost}')
        self.avg_cost = float(self.avg_cost)

    def market_value(self, price: float) -> float:
        return self.shares * float(price)

    def to_dict(self) -> Dict[str, Any]:
        return {'shares': self.shares, 'avg_cost': self.avg_cost, 'note': self.note}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Position':
        return cls(
            shares=int(data.get('shares', 0)),
            avg_cost=float(data.get('avg_cost', 0.0)),
            note=str(data.get('note', '')),
        )


@dataclass
class PortfolioState:
    """组合账户状态。"""

    cash: float = DEFAULT_CASH
    lot_size: int = DEFAULT_LOT_SIZE
    positions: Dict[str, Position] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION
    updated_at: str = field(default_factory=_now_iso)

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        if self.cash < 0:
            raise ValueError(f'现金必须非负，得到 {self.cash}')
        self.cash = float(self.cash)
        if self.lot_size <= 0:
            raise ValueError(f'lot_size 必须为正整数，得到 {self.lot_size}')
        self.lot_size = int(self.lot_size)
        for pos in self.positions.values():
            pos.validate()

    # ---- 估值 ----

    def holdings_value(self, prices: Dict[str, float]) -> float:
        """按提供的价格估算持仓总市值；缺失价格的标的按 0 计。"""
        total = 0.0
        for symbol, pos in self.positions.items():
            price = prices.get(symbol)
            if price is not None and price > 0:
                total += pos.market_value(price)
        return total

    def total_equity(self, prices: Dict[str, float]) -> float:
        """总权益 = 现金 + 持仓市值。"""
        return self.cash + self.holdings_value(prices)

    def position_value(self, symbol: str, price: float) -> float:
        pos = self.positions.get(symbol)
        return pos.market_value(price) if pos else 0.0

    # ---- 序列化 ----

    def to_dict(self) -> Dict[str, Any]:
        return {
            'schema_version': self.schema_version,
            'updated_at': self.updated_at,
            'cash': self.cash,
            'lot_size': self.lot_size,
            'positions': {s: p.to_dict() for s, p in self.positions.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PortfolioState':
        positions = {
            symbol: Position.from_dict(pdata)
            for symbol, pdata in (data.get('positions') or {}).items()
        }
        return cls(
            cash=float(data.get('cash', DEFAULT_CASH)),
            lot_size=int(data.get('lot_size', DEFAULT_LOT_SIZE)),
            positions=positions,
            schema_version=int(data.get('schema_version', SCHEMA_VERSION)),
            updated_at=str(data.get('updated_at') or _now_iso()),
        )


class PortfolioStateManager:
    """组合状态读写与编辑。

    所有写操作都会刷新 updated_at 并持久化到 JSON。
    """

    def __init__(self, path: Path = None, registry: StockRegistry = REGISTRY,
                 allow_unregistered: bool = False):
        self.path = Path(path) if path else Path('data/portfolio_state.json')
        self.registry = registry
        self.allow_unregistered = allow_unregistered

    # ---- 读 ----

    def load(self) -> PortfolioState:
        if not self.path.exists():
            return PortfolioState(cash=DEFAULT_CASH, lot_size=DEFAULT_LOT_SIZE,
                                  positions={})
        with open(self.path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return PortfolioState.from_dict(data)

    # ---- 写 ----

    def save(self, state: PortfolioState) -> PortfolioState:
        state.validate()
        state.updated_at = _now_iso()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        return state

    def _check_symbol(self, symbol: str) -> None:
        if self.allow_unregistered:
            return
        if not self.registry.is_registered(symbol):
            raise ValueError(f'股票 {symbol} 未在 stock_registry 中注册')

    def set_cash(self, amount: float) -> PortfolioState:
        if amount < 0:
            raise ValueError(f'现金必须非负，得到 {amount}')
        state = self.load()
        state.cash = float(amount)
        return self.save(state)

    def set_position(self, symbol: str, shares: int,
                     avg_cost: float = None, note: str = None) -> PortfolioState:
        self._check_symbol(symbol)
        state = self.load()
        existing = state.positions.get(symbol)
        new_avg = avg_cost if avg_cost is not None else (existing.avg_cost if existing else 0.0)
        new_note = note if note is not None else (existing.note if existing else '')
        state.positions[symbol] = Position(shares=shares, avg_cost=new_avg, note=new_note)
        return self.save(state)

    def remove_position(self, symbol: str) -> PortfolioState:
        state = self.load()
        state.positions.pop(symbol, None)
        return self.save(state)

    def set_lot_size(self, lot_size: int) -> PortfolioState:
        state = self.load()
        state.lot_size = lot_size
        return self.save(state)
