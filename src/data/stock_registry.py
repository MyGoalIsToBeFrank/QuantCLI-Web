"""
股票池注册表

维护所有可交易标的元数据，包括 symbol、名称、市场、数据源。
新增股票只需在此注册即可被 CLI / Web 识别。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class StockInfo:
    """股票元数据"""
    symbol: str                # Yahoo Finance / 数据源代码，如 '002156.SZ'
    name: str                  # 中文名称
    market: str                # 'A股' / '美股' / 'ETF'
    yf_symbol: Optional[str]   # yfinance 使用的 ticker，通常与 symbol 相同
    sector: Optional[str] = None
    benchmark: Optional[str] = None  # 基准指数，如 '000300.SS'
    active: bool = True


class StockRegistry:
    """股票池注册表"""

    _DEFAULT_STOCKS = [
        StockInfo(symbol='002156.SZ', name='通富微电', market='A股',
                  yf_symbol='002156.SZ', sector='半导体封装', benchmark='000300.SS'),
        StockInfo(symbol='601225.SS', name='陕西煤业', market='A股',
                  yf_symbol='601225.SS', sector='煤炭开采', benchmark='000300.SS'),
        StockInfo(symbol='300308.SZ', name='中际旭创', market='A股',
                  yf_symbol='300308.SZ', sector='半导体光模块', benchmark='000300.SS'),
        StockInfo(symbol='600460.SH', name='士兰微', market='A股',
                  yf_symbol='600460.SS', sector='半导体IDM', benchmark='000300.SS'),
        StockInfo(symbol='605358.SH', name='立昂微', market='A股',
                  yf_symbol='605358.SS', sector='半导体硅片', benchmark='000300.SS'),
        StockInfo(symbol='000725.SZ', name='京东方A', market='A股',
                  yf_symbol='000725.SZ', sector='显示面板', benchmark='000300.SS'),
        StockInfo(symbol='002185.SZ', name='华天科技', market='A股',
                  yf_symbol='002185.SZ', sector='半导体封测', benchmark='000300.SS'),
        StockInfo(symbol='AMD', name='AMD', market='美股',
                  yf_symbol='AMD', sector='半导体设计', benchmark='SPY'),
    ]

    def __init__(self):
        self._stocks: Dict[str, StockInfo] = {
            s.symbol: s for s in self._DEFAULT_STOCKS
        }

    def register(self, info: StockInfo) -> None:
        """注册新股票"""
        self._stocks[info.symbol] = info

    def get(self, symbol: str) -> StockInfo:
        """获取股票信息"""
        if symbol not in self._stocks:
            raise KeyError(f'未注册的股票: {symbol}')
        return self._stocks[symbol]

    def list_symbols(self) -> List[str]:
        """返回所有活跃股票代码"""
        return [s.symbol for s in self._stocks.values() if s.active]

    def list_all(self) -> List[StockInfo]:
        """返回所有活跃股票信息"""
        return [s for s in self._stocks.values() if s.active]

    def is_registered(self, symbol: str) -> bool:
        return symbol in self._stocks


# 全局实例
REGISTRY = StockRegistry()
