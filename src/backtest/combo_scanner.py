"""
全区间组合扫描器

对单只股票在所有 (pipeline, strategy) 组合中进行全区间回测，
按“最大回撤约束 + 收益最高”原则选出最佳组合。
"""

from typing import Dict, Any, List, Optional

from src.pipeline_registry import PIPELINE_REGISTRY
from src.strategy_registry import STRATEGY_REGISTRY
from src.backtest.combo_backtester import ComboBacktester


def scan_best_combo(symbol: str,
                    start_date: str = None,
                    end_date: str = None,
                    max_drawdown_pct: float = 5.0,
                    stop_loss_pct: float = None,
                    pipelines: List[str] = None,
                    strategies: List[str] = None,
                    initial_capital: float = 100000.0,
                    fee_per_trade: float = 5.0,
                    lot_size: int = 100) -> Dict[str, Any]:
    """
    扫描所有组合，返回满足回撤约束下收益最高的组合。

    返回：
        {
            'symbol': symbol,
            'best': metrics dict or None,
            'all_rankings': [metrics dict, ...],
            'constraint_relaxed': bool
        }
    """
    pipelines = pipelines or PIPELINE_REGISTRY.list_names()
    strategies = strategies or STRATEGY_REGISTRY.list_names()

    rankings = []
    for pname in pipelines:
        for sname in strategies:
            try:
                bt = ComboBacktester(
                    symbol, pname, sname,
                    initial_capital=initial_capital,
                    fee_per_trade=fee_per_trade,
                    lot_size=lot_size,
                    stop_loss_pct=stop_loss_pct
                )
                res = bt.run(start_date=start_date, end_date=end_date)
                rankings.append(res['metrics'])
            except Exception as e:
                rankings.append({
                    'symbol': symbol,
                    'pipeline': pname,
                    'strategy': sname,
                    'total_return_pct': -999,
                    'max_drawdown_pct': -999,
                    'error': str(e)
                })

    # 排序：收益优先，其次夏普，回撤越小越好
    rankings.sort(key=lambda x: (
        x.get('total_return_pct', -999),
        x.get('sharpe', 0),
        -x.get('max_drawdown_pct', 0)
    ), reverse=True)

    threshold = -abs(max_drawdown_pct)
    valid = [r for r in rankings
             if r.get('total_return_pct', -999) > -900
             and r.get('max_drawdown_pct', -999) > threshold]

    if valid:
        best = valid[0]
        relaxed = False
    else:
        # 无组合满足回撤约束，选择回撤最小者
        best = min([r for r in rankings if r.get('total_return_pct', -999) > -900],
                   key=lambda x: x.get('max_drawdown_pct', 0),
                   default=None)
        relaxed = True

    return {
        'symbol': symbol,
        'best': best,
        'all_rankings': rankings,
        'constraint_relaxed': relaxed
    }
