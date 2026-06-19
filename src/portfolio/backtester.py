"""
组合级（多股票联合）回测器

与单股 ComboBacktester 的关系：
  - ComboBacktester：单只股票、单一组合、独立资金。
  - PortfolioBacktester：一笔总资金在多只股票间联合分配，受组合风险约束
    （总仓位上限、单股上限、最低现金比例、按手取整），逐日滚动决策与成交。

成交语义沿用 ComboBacktester：每个交易日用"当日开盘价"作为已知信息
（当日 high/low/close 被遮蔽）做预测与决策，并在当日开盘价成交，避免前视。

输出：合并权益曲线、收益、最大回撤、回撤次数、交易记录与每日明细。

注意：默认只纳入交易日历一致的标的（同一数据源的 A 股）。跨市场标的
（如美股 AMD）日历不同，需显式传入 symbols 才纳入，并以日期交集对齐。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional

import pandas as pd

from src.data.data_manager import load_stock as _default_load_stock
from src.data.stock_registry import REGISTRY
from src.pipeline_registry import PIPELINE_REGISTRY
from src.strategy_registry import STRATEGY_REGISTRY
from src.analysis.best_combo_registry import BestComboRegistry
from src.backtest.combo_backtester import build_open_decision_frame
from src.backtest.metrics import calculate_metrics

from .risk import (
    RiskProfile, RiskProfileManager,
    count_drawdown_events, max_drawdown_pct, recent_volatility, score_candidate,
)
from .decision_engine import PortfolioDecisionEngine, CandidateDecision
from .state import PortfolioState, Position
from .schema import DecisionMode, DEFAULT_LOT_SIZE


class PortfolioBacktester:
    def __init__(self,
                 symbols: List[str] = None,
                 initial_capital: float = 100000.0,
                 fee_per_trade: float = 5.0,
                 lot_size: int = DEFAULT_LOT_SIZE,
                 risk_profile: RiskProfile = None,
                 best_combo_registry: BestComboRegistry = None,
                 pipeline_registry=PIPELINE_REGISTRY,
                 strategy_registry=STRATEGY_REGISTRY,
                 load_stock=_default_load_stock,
                 default_pipeline: str = 'ma_dual',
                 default_strategy: str = 'prob_position',
                 min_history: int = 60,
                 execution_price: str = 'close',
                 combo_plan: dict = None):
        self.symbols = symbols or REGISTRY.list_symbols()
        # walk-forward 组合计划：{symbol: [ComboChoice,...]}；提供时按日期解析组合，
        # 否则回退到 best_combos.json / 默认组合。
        self.combo_plan = combo_plan
        self.initial_capital = initial_capital
        self.fee = fee_per_trade
        self.lot_size = lot_size
        if execution_price not in ('close', 'open'):
            raise ValueError("execution_price 只能是 'close' 或 'open'")
        # 成交价：'close' 更贴近现实（收盘观察后成交），'open' 为旧的 T 开盘价语义
        self.execution_price = execution_price
        self.profile = risk_profile or RiskProfileManager().load()
        self.best_combo_registry = best_combo_registry or BestComboRegistry()
        self.pipeline_registry = pipeline_registry
        self.strategy_registry = strategy_registry
        self.load_stock = load_stock
        self.default_pipeline = default_pipeline
        self.default_strategy = default_strategy
        self.min_history = min_history
        # 复用决策引擎的分配器
        self._allocator = PortfolioDecisionEngine(
            best_combo_registry=self.best_combo_registry,
            pipeline_registry=self.pipeline_registry,
            strategy_registry=self.strategy_registry,
            load_stock=self.load_stock,
            default_pipeline=default_pipeline,
            default_strategy=default_strategy,
            fee=fee_per_trade,
        )

    # ------------------------------------------------------------------

    def _resolve_combo(self, symbol: str, on_date=None):
        # walk-forward 计划优先（按当日生效的组合，严格来自更早数据的选择）
        if self.combo_plan and symbol in self.combo_plan and on_date is not None:
            from .walkforward import combo_for_date
            ch = combo_for_date(self.combo_plan[symbol], on_date)
            if ch is not None:
                return ch.pipeline, ch.strategy
        combo = self.best_combo_registry.get(symbol)
        if combo:
            pl = combo.get('pipeline_name') or combo.get('pipeline')
            st = combo.get('strategy_id') or combo.get('strategy')
            if pl and st:
                return pl, st
        return self.default_pipeline, self.default_strategy

    def _make_pipeline(self, name: str):
        cache = getattr(self, '_pipe_cache', None)
        if cache is None:
            cache = self._pipe_cache = {}
        if name not in cache:
            cache[name] = self.pipeline_registry.create(name)
        return cache[name]

    def _make_strategy(self, name: str):
        cache = getattr(self, '_strat_cache', None)
        if cache is None:
            cache = self._strat_cache = {}
        if name not in cache:
            cache[name] = self.strategy_registry.create(name)
        return cache[name]

    def run(self, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        # 加载数据并按日期建立索引
        data: Dict[str, pd.DataFrame] = {}
        for symbol in self.symbols:
            try:
                df = self.load_stock(symbol).reset_index(drop=True)
            except Exception:
                continue
            if len(df) < self.min_history:
                continue
            data[symbol] = df

        if not data:
            raise ValueError('没有可用于组合回测的标的数据')

        # 主交易日历：纳入标的的日期交集，限定在 [start, end]
        date_sets = [set(df['date'].tolist()) for df in data.values()]
        common = set.intersection(*date_sets)
        master = sorted(d for d in common
                        if (start_date is None or str(d) >= str(start_date))
                        and (end_date is None or str(d) <= str(end_date)))
        if len(master) < 2:
            raise ValueError('纳入标的的共同交易日不足，无法回测（可能跨市场日历不一致）')

        # 每只标的的 date -> iloc 映射
        idx_of: Dict[str, Dict[Any, int]] = {
            s: {d: i for i, d in enumerate(df['date'].tolist())}
            for s, df in data.items()
        }

        cash = self.initial_capital
        shares: Dict[str, int] = {s: 0 for s in data}
        records = []
        trade_log = []

        for d in master:
            price_exec = {}
            price_close = {}
            candidates: List[CandidateDecision] = []

            for symbol, df in data.items():
                i = idx_of[symbol][d]
                if i < self.min_history:
                    continue
                c = float(df['close'].iloc[i])
                # 成交参考价：close=当日收盘（观察后成交），open=当日开盘
                px = c if self.execution_price == 'close' else float(df['open'].iloc[i])
                price_exec[symbol] = px
                price_close[symbol] = c
                # 按当日生效组合解析 pipeline/strategy（walk-forward 时随再平衡切换）
                pl, st = self._resolve_combo(symbol, on_date=d)
                cand = self._evaluate(symbol, df, i, px, shares[symbol], cash,
                                      price_exec, self._make_pipeline(pl), self._make_strategy(st))
                if cand is not None:
                    cand.pipeline, cand.strategy = pl, st
                    candidates.append(cand)

            if not price_exec:
                continue

            # 排序（风险优先）并打 rank
            selected = [c for c in candidates if c.selected]
            selected.sort(key=lambda x: x.final_rank, reverse=True)
            for r, c in enumerate(selected, start=1):
                c.rank = r

            # 用成交参考价构造当日状态并分配订单
            state = PortfolioState(
                cash=cash, lot_size=self.lot_size,
                positions={s: Position(shares=shares[s]) for s in shares if shares[s] > 0},
            )
            orders, _exposures, _late = self._allocator._allocate(
                state, self.profile, candidates, dict(price_exec),
                DecisionMode.CLOSE_AFTER_MARKET)

            # 成交
            for o in orders:
                sym = o['symbol']
                px = price_exec[sym]
                if o['action'] == 'buy':
                    cost = o['shares'] * px + self.fee
                    if cost <= cash:
                        cash -= cost
                        shares[sym] += o['shares']
                        trade_log.append({'date': str(d), 'symbol': sym, 'action': 'buy',
                                          'shares': o['shares'], 'price': round(px, 3),
                                          'reason': o['reason']})
                elif o['action'] == 'sell':
                    proceeds = o['shares'] * px - self.fee
                    cash += proceeds
                    shares[sym] = max(0, shares[sym] - o['shares'])
                    trade_log.append({'date': str(d), 'symbol': sym, 'action': 'sell',
                                      'shares': o['shares'], 'price': round(px, 3),
                                      'reason': o['reason']})

            # 收盘市值
            holdings = sum(shares[s] * price_close.get(s, 0.0) for s in shares)
            portfolio = cash + holdings
            exposure = holdings / portfolio if portfolio > 0 else 0.0
            records.append({
                'date': d,
                'cash': round(cash, 2),
                'holdings_value': round(holdings, 2),
                'portfolio': round(portfolio, 2),
                'stock_exposure': round(exposure, 4),
                'positions': sum(1 for s in shares if shares[s] > 0),
            })

        records_df = pd.DataFrame(records)
        equity = records_df['portfolio'].tolist()
        metrics = self._summarize(records_df, equity)
        metrics['initial_capital'] = self.initial_capital
        metrics['symbols'] = list(data.keys())
        # 报告每只标的"截至末日生效"的组合；walk-forward 下还附计划切换次数
        last_day = master[-1]
        combos_label = {}
        for s in data:
            pl, st = self._resolve_combo(s, on_date=last_day)
            label = f'{pl}+{st}'
            if self.combo_plan and s in self.combo_plan:
                label += f' (walk-forward, {len(self.combo_plan[s])} 段)'
            combos_label[s] = label
        metrics['combos'] = combos_label
        metrics['walk_forward'] = bool(self.combo_plan)

        return {
            'metrics': metrics,
            'records': records_df,
            'trades': trade_log,
        }

    def _evaluate(self, symbol, df, i, open_price, cur_shares, cash, price_open,
                  pipeline, strategy) -> Optional[CandidateDecision]:
        cand = CandidateDecision(symbol=symbol, current_shares=cur_shares,
                                 held=cur_shares > 0, reference_price=open_price)
        try:
            # 无前视：close 模式用截至当日的完整 bar（收盘已知）；open 模式遮蔽当日为开盘。
            if self.execution_price == 'close':
                decision_df = df.iloc[:i + 1].copy().reset_index(drop=True)
            else:
                decision_df = build_open_decision_frame(df, i)
            pipeline.fit(decision_df)
            pred = pipeline.predict()
        except Exception as e:
            pred = {'prob_bull': 0.5, 'signal': 'neutral', 'score': 0.0, 'note': str(e)}
        cand.prediction = {k: _native(v) for k, v in pred.items()}

        lookback = getattr(self.profile, 'risk_lookback_days', 120) or 120
        closes = df['close'].iloc[max(0, i - lookback + 1):i + 1].astype(float).tolist()
        volumes = df['volume'].iloc[max(0, i - lookback + 1):i + 1].astype(float).tolist()
        max_dd = max_drawdown_pct(closes)
        dd_events = count_drawdown_events(closes, threshold_pct=self.profile.drawdown_event_threshold_pct)
        vol = recent_volatility(closes)
        liq = 1.0 if (not volumes or sum(volumes[-20:]) <= 0) else 0.0
        cand.risk = {
            'max_drawdown_pct': round(max_dd, 2),
            'drawdown_events': dd_events,
            'recent_volatility': round(vol, 4),
            'liquidity_penalty': liq,
        }

        equity_hint = cash + cur_shares * open_price
        current_position = (cur_shares * open_price / equity_hint) if equity_hint > 0 else 0.0
        cand.current_position = current_position
        ctx = {
            'current_position': current_position, 'cash': cash, 'shares': cur_shares,
            'open_price': open_price, 'close_price': open_price,
            'prev_close': float(df['close'].iloc[i - 1]) if i > 0 else open_price,
            'fee_per_trade': self.fee, 'lot_size': self.lot_size, 'signal_threshold': 0.10,
        }
        try:
            decision = strategy.decide(pred, ctx)
            cand.target_position = float(decision.get('target_position', 0.0))
        except Exception:
            cand.target_position = current_position

        cand.score = score_candidate(cand.risk, pred, self.profile)
        single_limit = getattr(self.profile, 'single_drawdown_limit_pct', None) or self.profile.drawdown_limit_pct
        cand.risk_breach = abs(max_dd) > single_limit or dd_events > self.profile.max_drawdown_events
        cand.selected = not (cand.risk_breach and not cand.held)
        return cand

    @staticmethod
    def _summarize(records_df: pd.DataFrame, equity: List[float]) -> Dict[str, Any]:
        if records_df.empty:
            return {'total_return_pct': 0.0, 'max_drawdown_pct': 0.0,
                    'drawdown_events_3pct': 0, 'drawdown_events_5pct': 0, 'days': 0}
        initial = equity[0]
        final = equity[-1]
        total_return = (final / initial - 1) * 100 if initial else 0.0
        # 用每日组合权益计算交易次数/胜率近似
        daily = records_df['portfolio'].pct_change().dropna()
        win_rate = (daily > 0).mean() * 100 if len(daily) else 0.0
        sharpe = (daily.mean() / daily.std() * (252 ** 0.5)) if len(daily) > 1 and daily.std() > 0 else 0.0
        return {
            'total_return_pct': round(total_return, 2),
            'final_value': round(final, 2),
            'max_drawdown_pct': round(max_drawdown_pct(equity), 2),
            'drawdown_events_3pct': count_drawdown_events(equity, threshold_pct=3.0),
            'drawdown_events_5pct': count_drawdown_events(equity, threshold_pct=5.0),
            'avg_exposure': round(records_df['stock_exposure'].mean(), 4),
            'max_exposure': round(records_df['stock_exposure'].max(), 4),
            'win_rate': round(float(win_rate), 2),
            'sharpe': round(float(sharpe), 3),
            'start_date': str(records_df['date'].iloc[0]),
            'end_date': str(records_df['date'].iloc[-1]),
            'days': len(records_df),
        }


def _native(v):
    if hasattr(v, 'item'):
        try:
            return v.item()
        except Exception:
            return v
    return v
