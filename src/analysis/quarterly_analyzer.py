"""
季度策略分析器

对每个股票，按季度滚动回测所有 (pipeline, strategy) 组合，
选出每个季度的最佳组合，并生成排名报告。
"""

import os
import json
from datetime import datetime, date
from typing import List, Dict, Any
import pandas as pd

from src.backtest.combo_backtester import ComboBacktester
from src.pipeline_registry import PIPELINE_REGISTRY
from src.strategy_registry import STRATEGY_REGISTRY


class QuarterlyAnalyzer:
    def __init__(self, initial_capital: float = 100000.0,
                 fee_per_trade: float = 5.0, lot_size: int = 100):
        self.initial_capital = initial_capital
        self.fee_per_trade = fee_per_trade
        self.lot_size = lot_size

    def _quarters_between(self, start_date: str, end_date: str) -> List[tuple]:
        """生成季度区间列表 [(start, end), ...]"""
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        quarters = []
        current = date(start.year, (start.month - 1) // 3 * 3 + 1, 1)
        while current <= end:
            # 季度末
            q_end_month = current.month + 2
            q_end_year = current.year + (q_end_month - 1) // 12
            q_end_month = (q_end_month - 1) % 12 + 1
            q_end = date(q_end_year, q_end_month, 1)

            qs = max(current, start)
            qe = min(q_end, end)
            if qs <= qe:
                quarters.append((qs.isoformat(), qe.isoformat()))

            # 下一季度
            next_month = current.month + 3
            next_year = current.year + (next_month - 1) // 12
            next_month = (next_month - 1) % 12 + 1
            current = date(next_year, next_month, 1)

        return quarters

    def analyze_symbol(self, symbol: str, start_date: str, end_date: str,
                       pipelines: List[str] = None,
                       strategies: List[str] = None,
                       max_drawdown_pct: float = None) -> Dict[str, Any]:
        """
        对单只股票在指定区间内进行季度组合分析。

        参数：
            max_drawdown_pct: 最大回撤约束百分比（如 5.0 表示回撤不得超过 5%）。
                              若设置，则只考虑 max_drawdown_pct > -threshold 的组合；
                              若全部组合都不满足，则选择回撤最小者并标记放宽。

        返回：
            {
                'symbol': str,
                'quarters': [{
                    'quarter': '2024Q3',
                    'start': '2024-07-01',
                    'end': '2024-09-30',
                    'rankings': [metrics dicts],
                    'best': metrics dict,
                    'constraint_relaxed': bool
                }, ...]
            }
        """
        pipelines = pipelines or PIPELINE_REGISTRY.list_names()
        strategies = strategies or STRATEGY_REGISTRY.list_names()
        quarters = self._quarters_between(start_date, end_date)

        result = {'symbol': symbol, 'quarters': []}

        for qs, qe in quarters:
            quarter_label = self._quarter_label(qs)
            rankings = []

            for pname in pipelines:
                for sname in strategies:
                    try:
                        bt = ComboBacktester(
                            symbol, pname, sname,
                            self.initial_capital, self.fee_per_trade, self.lot_size
                        )
                        res = bt.run(start_date=qs, end_date=qe)
                        rankings.append(res['metrics'])
                    except Exception as e:
                        rankings.append({
                            'symbol': symbol,
                            'pipeline': pname,
                            'strategy': sname,
                            'quarter': quarter_label,
                            'total_return_pct': -999,
                            'error': str(e)
                        })

            # 排序：收益优先，其次夏普，再次最大回撤（越小越好）
            rankings.sort(key=lambda x: (
                x.get('total_return_pct', -999),
                x.get('sharpe', 0),
                -x.get('max_drawdown_pct', 0)
            ), reverse=True)

            # 应用最大回撤约束
            constraint_relaxed = False
            if max_drawdown_pct is not None:
                threshold = -abs(max_drawdown_pct)
                valid = [r for r in rankings if r.get('max_drawdown_pct', -999) > threshold]
                if valid:
                    best = valid[0]
                else:
                    # 全部不满足约束，选择回撤最小者
                    best = min(rankings,
                               key=lambda x: x.get('max_drawdown_pct', 0))
                    constraint_relaxed = True
            else:
                best = rankings[0] if rankings else None

            result['quarters'].append({
                'quarter': quarter_label,
                'start': qs,
                'end': qe,
                'rankings': rankings,
                'best': best,
                'constraint_relaxed': constraint_relaxed
            })

        return result

    def _quarter_label(self, date_str: str) -> str:
        d = date.fromisoformat(date_str)
        quarter = (d.month - 1) // 3 + 1
        return f'{d.year}Q{quarter}'

    def summarize(self, analysis: Dict[str, Any]) -> pd.DataFrame:
        """汇总每个季度的最佳组合"""
        rows = []
        for q in analysis['quarters']:
            best = q['best']
            if best:
                rows.append({
                    'quarter': q['quarter'],
                    'pipeline': best.get('pipeline'),
                    'strategy': best.get('strategy'),
                    'total_return_pct': best.get('total_return_pct'),
                    'max_drawdown_pct': best.get('max_drawdown_pct'),
                    'trade_count': best.get('trade_count'),
                    'sharpe': best.get('sharpe')
                })
        return pd.DataFrame(rows)
