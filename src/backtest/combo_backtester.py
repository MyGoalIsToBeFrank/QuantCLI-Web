"""
组合回测器

输入：股票 symbol + pipeline name + strategy name
过程：逐日滚动，pipeline 生成预测，strategy 生成决策，执行交易
输出：metrics + 每日 records
"""

import pandas as pd
from typing import Dict, Any

from src.data.data_manager import load_stock
from src.data.stock_registry import REGISTRY
from src.pipeline_registry import PIPELINE_REGISTRY
from src.strategy_registry import STRATEGY_REGISTRY
from src.strategy import calculate_trade_shares
from .metrics import calculate_metrics


def build_open_decision_frame(raw_df: pd.DataFrame, current_idx: int) -> pd.DataFrame:
    """Return data through current_idx with current row masked to known open only."""
    decision_df = raw_df.iloc[:current_idx + 1].copy().reset_index(drop=True)
    last = len(decision_df) - 1
    open_price = float(decision_df.loc[last, 'open'])
    decision_df.loc[last, 'high'] = open_price
    decision_df.loc[last, 'low'] = open_price
    decision_df.loc[last, 'close'] = open_price
    decision_df.loc[last, 'volume'] = 0
    return decision_df


def build_latest_open_decision_frame(raw_df: pd.DataFrame, open_price: float,
                                     decision_date=None) -> pd.DataFrame:
    """Mask or append the latest row so prediction can use a known open only."""
    decision_df = raw_df.copy().reset_index(drop=True)
    if decision_date is None:
        decision_date = decision_df['date'].iloc[-1]

    if str(decision_df['date'].iloc[-1]) == str(decision_date):
        last = len(decision_df) - 1
        decision_df.loc[last, 'open'] = float(open_price)
        decision_df.loc[last, 'high'] = float(open_price)
        decision_df.loc[last, 'low'] = float(open_price)
        decision_df.loc[last, 'close'] = float(open_price)
        decision_df.loc[last, 'volume'] = 0
        return decision_df

    new_row = {
        'date': decision_date,
        'open': float(open_price),
        'high': float(open_price),
        'low': float(open_price),
        'close': float(open_price),
        'volume': 0
    }
    return pd.concat([decision_df, pd.DataFrame([new_row])], ignore_index=True)


class ComboBacktester:
    def __init__(self, symbol: str, pipeline_name: str, strategy_name: str,
                 initial_capital: float = 100000.0, fee_per_trade: float = 5.0,
                 lot_size: int = 100, stop_loss_pct: float = None):
        self.symbol = symbol
        self.pipeline_name = pipeline_name
        self.strategy_name = strategy_name
        self.initial_capital = initial_capital
        self.fee_per_trade = fee_per_trade
        self.lot_size = lot_size
        self.stop_loss_pct = stop_loss_pct  # 组合回撤止损，如 0.05 表示 5%

    def run(self, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        from datetime import date

        raw_df = load_stock(self.symbol)
        if len(raw_df) < 60:
            raise ValueError(f'{self.symbol} 数据不足（{len(raw_df)} 行），无法回测')

        start_idx = 60
        if start_date:
            start = date.fromisoformat(start_date)
            mask = raw_df['date'] >= start
            start_idx = mask.idxmax() if mask.any() else 60
            start_idx = max(start_idx, 60)

        end_idx = len(raw_df)
        if end_date:
            end = date.fromisoformat(end_date)
            mask = raw_df['date'] <= end
            end_idx = mask[::-1].idxmax() + 1 if mask.any() else len(raw_df)

        # 回测区间截取为 [start_idx, end_idx)，但 fit 仍可使用 start_idx 之前的数据
        raw_df = raw_df.reset_index(drop=True)

        pipeline = PIPELINE_REGISTRY.create(self.pipeline_name)
        strategy = STRATEGY_REGISTRY.create(self.strategy_name)

        cash = self.initial_capital
        shares = 0
        total_fees = 0.0
        current_position = 0.0
        peak_portfolio = self.initial_capital
        records = []

        # 从 start_idx 开始，end_idx 结束
        for i in range(start_idx, end_idx):
            row = raw_df.iloc[i]
            current_date = row['date']
            close_price = float(row['close'])
            open_price = float(row['open'])

            # 滚动训练并预测
            decision_df = build_open_decision_frame(raw_df, i)
            pipeline.fit(decision_df)
            try:
                pred = pipeline.predict()
            except Exception as e:
                # 某些 pipeline 在数据不足时无法预测
                pred = {'score': 0.0, 'prob_bull': 0.5, 'signal': 'neutral', 'note': str(e)}

            # 策略决策
            context = {
                'current_position': current_position,
                'cash': cash,
                'shares': shares,
                'open_price': open_price,
                'close_price': close_price,
                'prev_close': float(raw_df.iloc[i - 1]['close']),
                'signal_threshold': 0.10,
                'fee_per_trade': self.fee_per_trade,
                'lot_size': self.lot_size
            }
            decision = strategy.decide(pred, context)
            target_position = decision['target_position']

            # 执行交易
            target_price = open_price  # T+1 开盘价成交
            trade_shares = calculate_trade_shares(
                cash, shares, target_price, target_position,
                self.fee_per_trade, self.lot_size
            )

            if trade_shares > 0:
                cost = trade_shares * target_price + self.fee_per_trade
                if cost <= cash:
                    cash -= cost
                    shares += trade_shares
                    total_fees += self.fee_per_trade
            elif trade_shares < 0:
                sell_shares = abs(trade_shares)
                proceeds = sell_shares * target_price - self.fee_per_trade
                cash += proceeds
                shares -= sell_shares
                total_fees += self.fee_per_trade

            portfolio = cash + shares * close_price

            # 组合回撤止损：若从峰值回撤超过阈值，清仓
            if self.stop_loss_pct is not None and portfolio > 0:
                if portfolio > peak_portfolio:
                    peak_portfolio = portfolio
                drawdown = (peak_portfolio - portfolio) / peak_portfolio
                if drawdown >= self.stop_loss_pct and shares > 0:
                    sell_shares = shares
                    proceeds = sell_shares * close_price - self.fee_per_trade
                    cash += proceeds
                    shares = 0
                    total_fees += self.fee_per_trade
                    portfolio = cash
                    current_position = 0.0

            current_position = shares * close_price / portfolio if portfolio > 0 else 0.0

            records.append({
                'date': current_date,
                'open': open_price,
                'close': close_price,
                'shares': shares,
                'cash': cash,
                'portfolio': portfolio,
                'total_fees': total_fees,
                'action': decision['action'],
                'target_position': target_position,
                'note': decision['note']
            })

        records_df = pd.DataFrame(records)
        metrics = calculate_metrics(records_df, self.initial_capital)
        benchmark_metrics = self._benchmark_metrics(
            start_date=metrics.get('start_date'),
            end_date=metrics.get('end_date')
        )
        metrics.update({
            'symbol': self.symbol,
            'pipeline': self.pipeline_name,
            'strategy': self.strategy_name,
            **benchmark_metrics
        })

        return {
            'metrics': metrics,
            'records': records_df
        }

    def _benchmark_metrics(self, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        try:
            info = REGISTRY.get(self.symbol)
            benchmark = info.benchmark
            if not benchmark:
                return {'benchmark_available': False, 'benchmark': None}
            bench_df = load_stock(benchmark)
        except Exception:
            return {'benchmark_available': False, 'benchmark': None}

        if start_date:
            bench_df = bench_df[bench_df['date'].astype(str) >= str(start_date)]
        if end_date:
            bench_df = bench_df[bench_df['date'].astype(str) <= str(end_date)]
        if bench_df.empty:
            return {'benchmark_available': False, 'benchmark': benchmark}

        first_open = float(bench_df['open'].iloc[0])
        if first_open <= 0:
            return {'benchmark_available': False, 'benchmark': benchmark}
        curve = bench_df['close'].astype(float) / first_open * self.initial_capital
        drawdown = (curve - curve.cummax()) / curve.cummax() * 100
        return {
            'benchmark_available': True,
            'benchmark': benchmark,
            'benchmark_return_pct': float((float(bench_df['close'].iloc[-1]) / first_open - 1) * 100),
            'benchmark_max_drawdown_pct': float(drawdown.min()),
        }
