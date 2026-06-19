"""
组合级决策引擎

编排流程：
  1. 读取账户状态与风险配置。
  2. 对每只注册股票做模式相关的逐股评估（pipeline 预测 + strategy 决策 + 风险度量）。
  3. 风险优先排序（先过滤再打分，回撤/回撤事件先于收益）。
  4. 在组合约束下分配目标仓位并生成按手取整的订单建议。
  5. 尾盘模式额外生成次日离场计划。

本引擎只产出"建议"，不下单。所有下层能力（数据、pipeline、strategy、
calculate_trade_shares）均被复用而非替换。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable

import pandas as pd

from src.data.data_manager import load_stock as _default_load_stock
from src.data.stock_registry import REGISTRY
from src.pipeline_registry import PIPELINE_REGISTRY
from src.strategy_registry import STRATEGY_REGISTRY
from src.analysis.best_combo_registry import BestComboRegistry

from .schema import DecisionMode, DEFAULT_LOT_SIZE
from .state import PortfolioStateManager, PortfolioState
from .risk import (
    RiskProfileManager, RiskProfile,
    count_drawdown_events, max_drawdown_pct, recent_volatility, score_candidate,
)
from .quotes import QuoteSnapshot, ManualQuoteProvider
from .modes import build_mode_frame

_CST = timezone(timedelta(hours=8))
_MIN_ROWS = 30


@dataclass
class CandidateDecision:
    """单只股票的候选决策与其评分。"""

    symbol: str
    pipeline: Optional[str] = None
    strategy: Optional[str] = None
    prediction: Dict[str, Any] = field(default_factory=dict)
    target_position: float = 0.0
    risk: Dict[str, Any] = field(default_factory=dict)
    score: Dict[str, Any] = field(default_factory=dict)
    reference_price: Optional[float] = None
    current_shares: int = 0
    current_position: float = 0.0
    held: bool = False
    risk_breach: bool = False
    selected: bool = False
    funded: bool = False
    rejected_reason: Optional[str] = None
    rank: Optional[int] = None

    @property
    def final_rank(self) -> float:
        return float(self.score.get('final_rank', -999.0))

    @property
    def opportunity_score(self) -> float:
        return float(self.score.get('opportunity_score', 0.0))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'pipeline': self.pipeline,
            'strategy': self.strategy,
            'prediction': self.prediction,
            'target_position': round(self.target_position, 4),
            'risk': self.risk,
            'score': self.score,
            'reference_price': self.reference_price,
            'current_shares': self.current_shares,
            'current_position': round(self.current_position, 4),
            'held': self.held,
            'risk_breach': self.risk_breach,
            'selected': self.selected,
            'funded': self.funded,
            'rejected_reason': self.rejected_reason,
            'rank': self.rank,
        }


class PortfolioDecisionEngine:
    def __init__(self,
                 state_manager: PortfolioStateManager = None,
                 risk_manager: RiskProfileManager = None,
                 registry=REGISTRY,
                 best_combo_registry: BestComboRegistry = None,
                 pipeline_registry=PIPELINE_REGISTRY,
                 strategy_registry=STRATEGY_REGISTRY,
                 load_stock: Callable = _default_load_stock,
                 default_pipeline: str = 'ma_dual',
                 default_strategy: str = 'prob_position',
                 fee: float = 5.0):
        self.state_manager = state_manager or PortfolioStateManager()
        self.risk_manager = risk_manager or RiskProfileManager()
        self.registry = registry
        self.best_combo_registry = best_combo_registry or BestComboRegistry()
        self.pipeline_registry = pipeline_registry
        self.strategy_registry = strategy_registry
        self.load_stock = load_stock
        self.default_pipeline = default_pipeline
        self.default_strategy = default_strategy
        self.fee = fee

    # ------------------------------------------------------------------
    # 组合资源解析
    # ------------------------------------------------------------------

    def _resolve_combo(self, symbol: str):
        combo = self.best_combo_registry.get(symbol)
        if combo:
            pipeline_name = combo.get('pipeline_name') or combo.get('pipeline')
            strategy_name = combo.get('strategy_id') or combo.get('strategy')
            if pipeline_name and strategy_name:
                return pipeline_name, strategy_name
        return self.default_pipeline, self.default_strategy

    def _latest_price(self, symbol: str) -> Optional[float]:
        try:
            df = self.load_stock(symbol)
            return float(df['close'].iloc[-1])
        except Exception:
            return None

    # ------------------------------------------------------------------
    # 逐股评估
    # ------------------------------------------------------------------

    def _evaluate_symbol(self, symbol: str, mode: str, state: PortfolioState,
                         profile: RiskProfile, quote_provider: ManualQuoteProvider,
                         open_prices: Dict[str, float], decision_date) -> CandidateDecision:
        position = state.positions.get(symbol)
        current_shares = position.shares if position else 0
        held = current_shares > 0
        cand = CandidateDecision(symbol=symbol, current_shares=current_shares, held=held)

        try:
            raw_df = self.load_stock(symbol)
        except Exception as e:
            cand.rejected_reason = f'data_load_failed: {e}'
            return cand

        if raw_df is None or len(raw_df) < _MIN_ROWS:
            cand.rejected_reason = 'insufficient_data'
            return cand

        pipeline_name, strategy_name = self._resolve_combo(symbol)
        cand.pipeline = pipeline_name
        cand.strategy = strategy_name

        # 模式数据帧
        try:
            snapshot = None
            if mode == DecisionMode.LATE_SESSION:
                if not quote_provider or not quote_provider.has(symbol):
                    cand.rejected_reason = 'missing_quote_snapshot'
                    return cand
                snapshot = quote_provider.get_snapshot(symbol)
            open_price = (open_prices or {}).get(symbol)
            mode_frame = build_mode_frame(
                mode, raw_df, open_price=open_price,
                snapshot=snapshot, decision_date=decision_date,
            )
        except Exception as e:
            cand.rejected_reason = f'mode_frame_failed: {e}'
            return cand

        cand.reference_price = mode_frame.reference_price

        # 预测
        try:
            pipeline = self.pipeline_registry.create(pipeline_name)
            pipeline.fit(mode_frame.frame)
            pred = pipeline.predict()
        except Exception as e:
            pred = {'prob_bull': 0.5, 'signal': 'neutral', 'score': 0.0, 'note': str(e)}
        cand.prediction = {k: _native(v) for k, v in pred.items()}

        # 风险度量（基于近窗口收盘价，使"历史回撤"限定在可比区间）
        lookback = getattr(profile, 'risk_lookback_days', 120) or 120
        closes_all = raw_df['close'].astype(float).tolist()
        closes = closes_all[-lookback:] if lookback > 0 else closes_all
        volumes = raw_df['volume'].astype(float).tolist() if 'volume' in raw_df.columns else []
        max_dd = max_drawdown_pct(closes)
        dd_events = count_drawdown_events(closes, threshold_pct=profile.drawdown_event_threshold_pct)
        vol = recent_volatility(closes)
        liquidity_penalty = self._liquidity_penalty(volumes)
        data_age_days = self._data_age_days(raw_df, mode_frame.decision_date)
        risk_metrics = {
            'max_drawdown_pct': round(max_dd, 2),
            'drawdown_events': dd_events,
            'recent_volatility': round(vol, 4),
            'liquidity_penalty': round(liquidity_penalty, 4),
            'data_age_days': data_age_days,
        }
        cand.risk = risk_metrics

        # 策略决策（带真实持仓上下文）
        equity_for_ctx = state.total_equity(self._equity_price_hint(state, symbol, mode_frame.reference_price))
        current_position = 0.0
        if held and mode_frame.reference_price and equity_for_ctx > 0:
            current_position = current_shares * mode_frame.reference_price / equity_for_ctx
        cand.current_position = current_position

        context = {
            'current_position': current_position,
            'cash': state.cash,
            'shares': current_shares,
            'open_price': mode_frame.reference_price,
            'close_price': mode_frame.reference_price,
            'prev_close': mode_frame.prev_close,
            'fee_per_trade': self.fee,
            'lot_size': state.lot_size,
            'signal_threshold': 0.10,
        }
        try:
            strategy = self.strategy_registry.create(strategy_name)
            decision = strategy.decide(pred, context)
            cand.target_position = float(decision.get('target_position', 0.0))
        except Exception as e:
            cand.target_position = current_position
            cand.prediction.setdefault('note', str(e))

        # 评分
        cand.score = score_candidate(risk_metrics, pred, profile)

        # 硬性风险过滤：个股价格回撤用更现实的 single_drawdown_limit_pct，
        # 回撤事件数用 max_drawdown_events。drawdown_limit_pct 留作组合级权益约束。
        single_limit = getattr(profile, 'single_drawdown_limit_pct', None) or profile.drawdown_limit_pct
        cand.risk_breach = (
            abs(max_dd) > single_limit
            or dd_events > profile.max_drawdown_events
        )
        if cand.risk_breach and not held:
            cand.rejected_reason = 'risk_limit_exceeded'
            cand.selected = False
        else:
            cand.selected = True
        return cand

    @staticmethod
    def _equity_price_hint(state: PortfolioState, symbol: str, price: float) -> Dict[str, float]:
        """为权益估算提供价格提示（当前仅填充被评估标的的价格）。"""
        hint = {}
        if price:
            hint[symbol] = price
        return hint

    @staticmethod
    def _liquidity_penalty(volumes: List[float]) -> float:
        if not volumes:
            return 1.0
        recent = volumes[-20:]
        avg = sum(recent) / len(recent) if recent else 0.0
        return 1.0 if avg <= 0 else 0.0

    @staticmethod
    def _data_age_days(raw_df: pd.DataFrame, decision_date) -> Optional[int]:
        try:
            last = raw_df['date'].iloc[-1]
            last_d = last if hasattr(last, 'year') else datetime.fromisoformat(str(last)).date()
            ref = decision_date if hasattr(decision_date, 'year') else last_d
            return (ref - last_d).days if ref else 0
        except Exception:
            return None

    # ------------------------------------------------------------------
    # 主决策
    # ------------------------------------------------------------------

    def decide(self, mode: str, symbols: List[str] = None,
               quotes: Dict[str, Any] = None,
               open_prices: Dict[str, float] = None,
               decision_date=None) -> Dict[str, Any]:
        DecisionMode.validate(mode)
        state = self.state_manager.load()
        profile = self.risk_manager.load()
        universe = symbols or self.registry.list_symbols()
        quote_provider = ManualQuoteProvider(quotes) if quotes else ManualQuoteProvider()

        candidates: List[CandidateDecision] = []
        price_map: Dict[str, float] = {}
        for symbol in universe:
            cand = self._evaluate_symbol(symbol, mode, state, profile,
                                         quote_provider, open_prices, decision_date)
            candidates.append(cand)
            if cand.reference_price:
                price_map[symbol] = cand.reference_price

        # 持有但不在 universe 的标的，补充价格用于权益与敞口估算
        for symbol in state.positions:
            if symbol not in price_map:
                price = self._latest_price(symbol)
                if price:
                    price_map[symbol] = price

        # 风险优先排序 + 收益感知选股（少而精）
        self.rank_and_fund(candidates, profile)

        orders, exposures, late_plan = self._allocate(
            state, profile, candidates, price_map, mode
        )

        equity = state.total_equity(price_map)
        return {
            'mode': mode,
            'timestamp': datetime.now(_CST).replace(microsecond=0).isoformat(),
            'portfolio': {
                'cash': round(state.cash, 2),
                'estimated_equity': round(equity, 2),
                'current_stock_exposure': exposures['current'],
                'target_stock_exposure': exposures['target'],
                'cash_after_trades': exposures['cash_after'],
                'lot_size': state.lot_size,
            },
            'risk_profile': profile.to_dict(),
            'orders': orders,
            'candidates': [c.to_dict() for c in sorted(
                candidates, key=lambda c: (c.rank if c.rank else 9999))],
            'late_session_plan': late_plan,
        }

    @staticmethod
    def rank_and_fund(candidates: List[CandidateDecision], profile: RiskProfile):
        """对通过风险闸门的候选排序，并按"少而精"选股拨款（设置 rank 与 funded）。

        - 排序：按 final_rank 降序（风险优先 + 机会分）。
        - 拨款（funded）：仅给"想买且机会分达标"的**前 K 名**（K = max_holdings）。
          其余持仓维持、不追加，新资金不摊向弱标的。
        """
        selected = [c for c in candidates if c.selected]
        selected.sort(key=lambda c: c.final_rank, reverse=True)
        for i, c in enumerate(selected, start=1):
            c.rank = i
            c.funded = False

        floor = getattr(profile, 'min_opportunity_score', 0.0) or 0.0
        max_holdings = getattr(profile, 'max_holdings', 0) or len(selected)
        eligible = [
            c for c in selected
            if c.opportunity_score >= floor and c.target_position > c.current_position
        ]
        for c in eligible[:max_holdings]:
            c.funded = True
        return selected

    # ------------------------------------------------------------------
    # 分配与下单
    # ------------------------------------------------------------------

    def _allocate(self, state: PortfolioState, profile: RiskProfile,
                  candidates: List[CandidateDecision], price_map: Dict[str, float],
                  mode: str):
        lot = state.lot_size
        equity = state.total_equity(price_map)
        if equity <= 0:
            equity = state.cash

        min_cash = profile.min_cash_ratio * equity
        max_total_value = profile.max_total_position * equity
        max_single_value = profile.max_single_position * equity
        max_late_value = profile.max_late_session_position * equity

        cand_by_symbol = {c.symbol: c for c in candidates}

        # 工作副本
        shares_map: Dict[str, int] = {s: p.shares for s, p in state.positions.items()}
        cash_avail = state.cash

        def cur_value(symbol: str) -> float:
            price = price_map.get(symbol)
            return shares_map.get(symbol, 0) * price if price else 0.0

        current_stock_value = sum(cur_value(s) for s in shares_map)

        # 每只标的的目标市值
        target_values: Dict[str, float] = {}
        for symbol, price in price_map.items():
            cand = cand_by_symbol.get(symbol)
            cur_shares = shares_map.get(symbol, 0)
            cur_val = cur_shares * price
            if cand is None:
                target_values[symbol] = cur_val  # 持有但未评估，保持
                continue
            if cand.held and cand.risk_breach:
                target_values[symbol] = 0.0       # 触及风险红线，清仓
            elif cand.selected:
                target_values[symbol] = min(cand.target_position * equity, max_single_value)
            elif cand.held:
                target_values[symbol] = cur_val   # 被拒但持有：保持
            else:
                target_values[symbol] = 0.0

        orders: List[Dict[str, Any]] = []

        # 1) 先卖出/减仓（释放现金、降低风险）
        for symbol, price in price_map.items():
            cur_shares = shares_map.get(symbol, 0)
            if cur_shares <= 0 or price <= 0:
                continue
            target_val = target_values.get(symbol, cur_shares * price)
            target_shares = self._round_lot(target_val / price, lot)
            if target_shares < cur_shares:
                sell_shares = cur_shares - target_shares
                proceeds = sell_shares * price - self.fee
                cash_avail += proceeds
                shares_map[symbol] = target_shares
                current_stock_value -= sell_shares * price
                orders.append(self._make_order(
                    symbol, 'sell', sell_shares, price, proceeds,
                    target_values.get(symbol, 0.0) / equity if equity else 0.0,
                    cand_by_symbol.get(symbol)))

        # 2) 再买入（按风险优先排名）
        buy_cands = sorted(
            [c for c in candidates if c.selected and c.rank],
            key=lambda c: c.rank)
        running_late_value = 0.0
        for cand in buy_cands:
            symbol = cand.symbol
            price = price_map.get(symbol)
            if not price or price <= 0:
                continue
            cur_shares = shares_map.get(symbol, 0)
            cur_val = cur_shares * price
            desired_val = min(target_values.get(symbol, 0.0), max_single_value)
            if desired_val <= cur_val:
                continue
            add_val = desired_val - cur_val
            add_val = min(add_val, max_total_value - current_stock_value)
            add_val = min(add_val, max(0.0, cash_avail - min_cash - self.fee))
            if mode == DecisionMode.LATE_SESSION:
                add_val = min(add_val, max_late_value - running_late_value)
            if add_val <= 0:
                continue
            buy_shares = self._round_lot(add_val / price, lot)
            # 现金兜底
            while buy_shares > 0 and buy_shares * price + self.fee > cash_avail:
                buy_shares -= lot
            if buy_shares <= 0:
                continue
            cost = buy_shares * price + self.fee
            cash_avail -= cost
            shares_map[symbol] = cur_shares + buy_shares
            current_stock_value += buy_shares * price
            running_late_value += buy_shares * price
            orders.append(self._make_order(
                symbol, 'buy', buy_shares, price, -cost,
                target_values.get(symbol, 0.0) / equity if equity else 0.0,
                cand))

        # 敞口汇总
        final_stock_value = sum(cur_value(s) for s in shares_map)
        current_exposure = sum(
            state.positions[s].shares * price_map.get(s, 0.0)
            for s in state.positions if price_map.get(s)
        ) / equity if equity else 0.0
        exposures = {
            'current': round(current_exposure, 4),
            'target': round(final_stock_value / equity, 4) if equity else 0.0,
            'cash_after': round(cash_avail, 2),
        }

        late_plan = self._late_session_plan(orders, profile) if mode == DecisionMode.LATE_SESSION else []
        return orders, exposures, late_plan

    def _make_order(self, symbol, action, shares, price, cash_change,
                    target_position, cand: CandidateDecision):
        reason = self._order_reason(action, cand)
        return {
            'symbol': symbol,
            'action': action,
            'shares': int(shares),
            'price': round(float(price), 4),
            'estimated_cash_change': round(float(cash_change), 2),
            'target_position': round(float(target_position), 4),
            'reason': reason,
        }

    @staticmethod
    def _order_reason(action: str, cand: Optional[CandidateDecision]) -> str:
        if cand is None:
            return 'rebalance to target'
        if action == 'sell' and cand.risk_breach:
            return 'risk limit breached, trim/exit'
        risk = cand.risk or {}
        signal = (cand.prediction or {}).get('signal', 'neutral')
        return (f'signal={signal}, max_drawdown={risk.get("max_drawdown_pct")}%, '
                f'drawdown_events={risk.get("drawdown_events")}, '
                f'rank={cand.rank}')

    def _late_session_plan(self, orders: List[Dict[str, Any]],
                           profile: RiskProfile) -> List[Dict[str, Any]]:
        plan = []
        tp = profile.late_session_take_profit_pct / 100.0
        for order in orders:
            if order['action'] != 'buy':
                continue
            entry = order['price']
            plan.append({
                'symbol': order['symbol'],
                'entry_price': entry,
                'take_profit_price': round(entry * (1 + tp), 4),
                'fallback_exit': profile.late_session_exit,
            })
        return plan

    @staticmethod
    def _round_lot(shares: float, lot_size: int) -> int:
        if lot_size <= 0:
            lot_size = 1
        return (max(0, int(math.floor(shares))) // lot_size) * lot_size


def _native(v):
    if hasattr(v, 'item'):
        try:
            return v.item()
        except Exception:
            return v
    return v
