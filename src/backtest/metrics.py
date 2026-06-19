"""
回测指标计算
"""

import pandas as pd
import numpy as np


def calculate_metrics(records: pd.DataFrame, initial_capital: float) -> dict:
    """
    根据每日记录计算回测指标。

    records 必须包含列：
        date, portfolio, total_fees
    """
    if records.empty:
        return {
            'total_return_pct': 0.0,
            'max_drawdown_pct': 0.0,
            'buy_hold_return_pct': 0.0,
            'buy_hold_max_drawdown_pct': 0.0,
            'excess_return_pct': 0.0,
            'beats_buy_hold': False,
            'trade_count': 0,
            'win_rate': 0.0,
            'sharpe': 0.0,
            'start_date': None,
            'end_date': None,
            'days': 0
        }

    final_value = records['portfolio'].iloc[-1]
    total_return = (final_value / initial_capital - 1) * 100
    buy_hold_return = 0.0
    buy_hold_max_drawdown = 0.0
    if 'open' in records.columns and 'close' in records.columns:
        first_open = float(records['open'].iloc[0])
        if first_open > 0:
            buy_hold_curve = records['close'].astype(float) / first_open * initial_capital
            buy_hold_return = (float(records['close'].iloc[-1]) / first_open - 1) * 100
            buy_hold_cummax = buy_hold_curve.cummax()
            buy_hold_drawdown = (buy_hold_curve - buy_hold_cummax) / buy_hold_cummax * 100
            buy_hold_max_drawdown = buy_hold_drawdown.min()

    # 最大回撤
    cummax = records['portfolio'].cummax()
    drawdown = (records['portfolio'] - cummax) / cummax * 100
    max_drawdown = drawdown.min()

    # 交易次数（通过 shares 变化判断）
    trades = records['shares'].diff().fillna(records['shares'].iloc[0]).abs()
    trade_count = int((trades > 0).sum())

    # 胜率：每次买入后对应卖出是否盈利（简化：基于 portfolio 增长判断）
    # 更精确的胜率需要交易对，这里用每日收益为正的天数占比近似
    daily_returns = records['portfolio'].pct_change().dropna()
    win_rate = (daily_returns > 0).mean() * 100 if len(daily_returns) > 0 else 0.0

    # 夏普（简化：日收益 / 日收益标准差 * sqrt(252)）
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
    else:
        sharpe = 0.0

    return {
        'total_return_pct': float(total_return),
        'max_drawdown_pct': float(max_drawdown),
        'buy_hold_return_pct': float(buy_hold_return),
        'buy_hold_max_drawdown_pct': float(buy_hold_max_drawdown),
        'excess_return_pct': float(total_return - buy_hold_return),
        'beats_buy_hold': bool(total_return > buy_hold_return),
        'trade_count': trade_count,
        'win_rate': float(win_rate),
        'sharpe': float(sharpe),
        'final_value': float(final_value),
        'total_fees': float(records['total_fees'].iloc[-1]),
        'start_date': str(records['date'].iloc[0]),
        'end_date': str(records['date'].iloc[-1]),
        'days': len(records)
    }
