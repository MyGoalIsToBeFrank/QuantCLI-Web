"""
Walk-forward 组合选择器

核心纪律（用户反馈）：**调参/组合选择不得前视**。
在每个再平衡点 t，只用 `< t` 的数据为每只标的选出组合；该组合用于 [t, 下一个再平衡点) 的
前向区间。前向区间对所选组合而言是**样本外**的。

输出一份按时间排列的"组合计划"，回测器据此在每个交易日读取当时生效的组合，
从而保证"选得对不对"可以被诚实评估。

为控制运行时间，候选组合默认是一份精选短名单，可覆盖。评分指标默认 Sharpe，
也可按"收益/回撤"等风险调整口径。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Tuple, Callable, Optional, Any

# 精选候选组合（pipeline, strategy）；均为已验证可运行、策略接受 prob_bull。
DEFAULT_CANDIDATES: List[Tuple[str, str]] = [
    ('ma_dual', 'prob_position'),
    ('ma_dual', 'low_risk'),
    ('rsi', 'low_risk'),
    ('macd', 'low_risk'),
    ('boll', 'low_risk'),
    ('dt_logistic', 'prob_position'),
]


@dataclass
class ComboChoice:
    """某再平衡点选出的组合及其训练窗口绩效。"""

    effective_from: date
    pipeline: str
    strategy: str
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'effective_from': str(self.effective_from),
            'pipeline': self.pipeline,
            'strategy': self.strategy,
            'metrics': self.metrics,
        }


def combo_for_date(choices: List[ComboChoice], d) -> Optional[ComboChoice]:
    """返回在日期 d 生效的组合（effective_from <= d 的最后一个）。"""
    chosen = None
    for ch in choices:
        if ch.effective_from <= d:
            chosen = ch
        else:
            break
    return chosen


def _to_date(x) -> date:
    if isinstance(x, date):
        return x
    return date.fromisoformat(str(x)[:10])


class WalkForwardSelector:
    def __init__(self,
                 candidate_combos: List[Tuple[str, str]] = None,
                 train_window_days: int = 180,
                 step_days: int = 63,
                 metric: str = 'sharpe',
                 min_trades: int = 3,
                 initial_capital: float = 100000.0,
                 fee_per_trade: float = 5.0,
                 lot_size: int = 100,
                 scorer: Callable = None):
        self.candidate_combos = candidate_combos or list(DEFAULT_CANDIDATES)
        self.train_window_days = train_window_days
        self.step_days = step_days
        self.metric = metric
        self.min_trades = min_trades
        self.initial_capital = initial_capital
        self.fee_per_trade = fee_per_trade
        self.lot_size = lot_size
        self.scorer = scorer or self._default_scorer

    # ------------------------------------------------------------------

    def _default_scorer(self, symbol: str, pipeline: str, strategy: str,
                        start: date, end: date) -> Dict[str, Any]:
        """用 ComboBacktester 在 [start, end] 训练窗口上回测，返回 metrics。"""
        from src.backtest.combo_backtester import ComboBacktester
        bt = ComboBacktester(
            symbol, pipeline, strategy,
            initial_capital=self.initial_capital,
            fee_per_trade=self.fee_per_trade,
            lot_size=self.lot_size,
        )
        return bt.run(start_date=str(start), end_date=str(end))['metrics']

    def _score(self, metrics: Dict[str, Any]) -> float:
        if self.metric == 'sharpe':
            return float(metrics.get('sharpe', 0.0))
        if self.metric == 'return':
            return float(metrics.get('total_return_pct', 0.0))
        if self.metric == 'return_dd':
            ret = float(metrics.get('total_return_pct', 0.0))
            dd = abs(float(metrics.get('max_drawdown_pct', 0.0)))
            return ret / (1.0 + dd)
        return float(metrics.get('sharpe', 0.0))

    def select_at(self, symbol: str, cutoff) -> Optional[ComboChoice]:
        """在再平衡点 cutoff，仅用 `< cutoff` 的数据选出最佳组合。"""
        cutoff = _to_date(cutoff)
        train_start = cutoff - timedelta(days=self.train_window_days)
        train_end = cutoff - timedelta(days=1)  # 严格早于 cutoff
        best = None
        for pl, st in self.candidate_combos:
            try:
                m = self.scorer(symbol, pl, st, train_start, train_end)
            except Exception:
                continue
            if m is None:
                continue
            if int(m.get('trade_count', 0)) < self.min_trades:
                continue
            score = self._score(m)
            if best is None or score > best[0]:
                best = (score, pl, st, m)
        if best is None:
            return None
        return ComboChoice(cutoff, best[1], best[2], best[3])

    def rebalance_dates(self, start, end) -> List[date]:
        start, end = _to_date(start), _to_date(end)
        dates = []
        d = start
        while d <= end:
            dates.append(d)
            d = d + timedelta(days=self.step_days)
        return dates

    def build_plan(self, symbols: List[str], start, end) -> Dict[str, List[ComboChoice]]:
        """为每只标的构造按时间排列的组合计划。"""
        plan: Dict[str, List[ComboChoice]] = {}
        for symbol in symbols:
            choices: List[ComboChoice] = []
            for rd in self.rebalance_dates(start, end):
                ch = self.select_at(symbol, rd)
                if ch is not None:
                    choices.append(ch)
            plan[symbol] = choices
        return plan
