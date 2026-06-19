"""
通用交易工具函数

被 ComboBacktester、CLI 决策、API 决策共享，
负责把目标仓位翻译为实际可成交股数。
"""


def _round_lot(shares, lot_size):
    """将股数向下对齐到 lot_size 的整数倍"""
    if lot_size <= 0:
        lot_size = 1
    return (max(0, int(shares)) // lot_size) * lot_size


def calculate_trade_shares(cash, shares, current_price, position_ratio, fee=5.0, lot_size=1):
    """
    计算需要买卖的股数（按手数离散化）

    参数:
        cash: 当前现金
        shares: 当前持股
        current_price: 当前股价
        position_ratio: 目标仓位比例（0.0 ~ 1.0）
        fee: 单边手续费
        lot_size: 每手股数（A股默认100）

    返回:
        trade_shares: 正=买入，负=卖出，0=不交易
    """
    total_value = cash + shares * current_price
    target_value = position_ratio * total_value
    target_shares = _round_lot(target_value / current_price, lot_size)
    trade_shares = target_shares - shares

    if trade_shares > 0:
        cost = trade_shares * current_price + fee
        if cost > cash:
            max_shares = _round_lot((cash - fee) / current_price, lot_size)
            trade_shares = max_shares - shares
            if trade_shares <= 0:
                trade_shares = 0

    if trade_shares < 0:
        trade_shares = -_round_lot(abs(trade_shares), lot_size)

    return trade_shares
