"""
实时行情快照与行情提供者

V1 仅需 ManualQuoteProvider（手动录入）。后续可在同一 QuoteProvider
接口下实现 YFinanceIntradayProvider 等，无需改动决策层。

校验规则（section 9）：
  - timestamp 必须存在
  - price/open/high/low 必须为正
  - low <= price <= high
  - prev_close > 0
  - 过期快照可被拒绝或告警
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

_CST = timezone(timedelta(hours=8))


def _parse_timestamp(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_CST)
        return dt
    except (ValueError, TypeError):
        return None


@dataclass
class QuoteSnapshot:
    """单只股票的盘中行情快照。"""

    symbol: str
    timestamp: str
    price: float
    open: float
    high: float
    low: float
    prev_close: float
    volume: float = 0.0
    source: str = 'manual'
    granularity: str = 'tail'

    def validate(self) -> None:
        if not self.timestamp or _parse_timestamp(self.timestamp) is None:
            raise ValueError(f'{self.symbol} 行情快照缺少有效 timestamp')
        for name in ('price', 'open', 'high', 'low'):
            value = getattr(self, name)
            if value is None or float(value) <= 0:
                raise ValueError(f'{self.symbol} 行情快照 {name} 必须为正，得到 {value}')
        if float(self.prev_close) <= 0:
            raise ValueError(f'{self.symbol} 行情快照 prev_close 必须为正，得到 {self.prev_close}')
        if not (self.low <= self.price <= self.high):
            raise ValueError(
                f'{self.symbol} 行情快照不满足 low<=price<=high: '
                f'low={self.low} price={self.price} high={self.high}'
            )

    def is_stale(self, max_age_minutes: float = 120.0,
                 now: datetime = None) -> bool:
        """快照是否过期（超过 max_age_minutes）。"""
        dt = _parse_timestamp(self.timestamp)
        if dt is None:
            return True
        now = now or datetime.now(_CST)
        if now.tzinfo is None:
            now = now.replace(tzinfo=_CST)
        age = (now - dt).total_seconds() / 60.0
        return age > max_age_minutes

    def gap_pct(self) -> float:
        if self.prev_close > 0:
            return (self.price / self.prev_close - 1.0) * 100.0
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp,
            'price': float(self.price),
            'open': float(self.open),
            'high': float(self.high),
            'low': float(self.low),
            'volume': float(self.volume),
            'prev_close': float(self.prev_close),
            'source': self.source,
            'granularity': self.granularity,
        }

    @classmethod
    def from_dict(cls, symbol: str, data: Dict[str, Any]) -> 'QuoteSnapshot':
        return cls(
            symbol=data.get('symbol', symbol),
            timestamp=str(data.get('timestamp', '')),
            price=float(data.get('price', 0.0)),
            open=float(data.get('open', 0.0)),
            high=float(data.get('high', 0.0)),
            low=float(data.get('low', 0.0)),
            prev_close=float(data.get('prev_close', 0.0)),
            volume=float(data.get('volume', 0.0) or 0.0),
            source=str(data.get('source', 'manual')),
            granularity=str(data.get('granularity', 'tail')),
        )


class QuoteProvider:
    """行情提供者接口。"""

    def get_snapshot(self, symbol: str) -> QuoteSnapshot:  # pragma: no cover - 接口
        raise NotImplementedError


class ManualQuoteProvider(QuoteProvider):
    """从预先提供的 dict 中取快照（CLI/WebUI/API 手动录入）。"""

    def __init__(self, quotes: Dict[str, Any] = None):
        self._quotes: Dict[str, QuoteSnapshot] = {}
        for symbol, data in (quotes or {}).items():
            if isinstance(data, QuoteSnapshot):
                self._quotes[symbol] = data
            else:
                self._quotes[symbol] = QuoteSnapshot.from_dict(symbol, data)

    def has(self, symbol: str) -> bool:
        return symbol in self._quotes

    def get_snapshot(self, symbol: str) -> QuoteSnapshot:
        if symbol not in self._quotes:
            raise KeyError(f'未提供 {symbol} 的行情快照')
        return self._quotes[symbol]
