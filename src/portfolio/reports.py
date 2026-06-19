"""
组合决策结果的格式化助手（CLI/API/WebUI 友好）

不做颜色处理，颜色由 CLI 层叠加；这里只把决策结果整理为可读文本块。
"""

from __future__ import annotations

from typing import Dict, Any, List


def format_state(state_dict: Dict[str, Any], prices: Dict[str, float] = None) -> str:
    prices = prices or {}
    lines = []
    lines.append(f"现金: {state_dict['cash']:.2f}")
    lines.append(f"每手股数 (lot_size): {state_dict['lot_size']}（锁定）")
    lines.append(f"更新时间: {state_dict.get('updated_at', 'N/A')}")
    positions = state_dict.get('positions', {})
    if not positions:
        lines.append('持仓: 无')
        return '\n'.join(lines)
    lines.append('持仓:')
    lines.append(f"  {'代码':<12}{'股数':>10}{'成本':>10}{'最新价':>10}{'市值':>14}  备注")
    for symbol, pos in positions.items():
        price = prices.get(symbol)
        price_str = f'{price:.2f}' if price else 'N/A'
        mv = pos['shares'] * price if price else 0.0
        lines.append(
            f"  {symbol:<12}{pos['shares']:>10}{pos['avg_cost']:>10.2f}"
            f"{price_str:>10}{mv:>14.2f}  {pos.get('note', '')}"
        )
    return '\n'.join(lines)


def format_decision(result: Dict[str, Any]) -> str:
    lines = []
    p = result['portfolio']
    lines.append(f"模式: {result['mode']}    时间: {result['timestamp']}")
    lines.append(
        f"现金: {p['cash']:.2f}  预估权益: {p['estimated_equity']:.2f}  "
        f"当前股票敞口: {p['current_stock_exposure']*100:.1f}%  "
        f"目标股票敞口: {p['target_stock_exposure']*100:.1f}%"
    )
    lines.append(f"交易后现金: {p['cash_after_trades']:.2f}")
    lines.append('')

    orders = result.get('orders', [])
    lines.append(f"== 订单建议 ({len(orders)}) ==")
    if not orders:
        lines.append('  无建议交易')
    else:
        for o in orders:
            lines.append(
                f"  [{o['action'].upper():<4}] {o['symbol']:<12} "
                f"{o['shares']:>6} 股 @ {o['price']:.2f}  "
                f"现金变动 {o['estimated_cash_change']:+.2f}  | {o['reason']}"
            )
    lines.append('')

    lines.append('== 候选明细（风险优先排序） ==')
    for c in result.get('candidates', []):
        flag = '选中' if c['selected'] else f"拒绝({c.get('rejected_reason')})"
        rank = c.get('rank')
        rank_str = f"#{rank}" if rank else '-'
        risk = c.get('risk', {})
        score = c.get('score', {})
        lines.append(
            f"  {rank_str:<4} {c['symbol']:<12} {flag:<22} "
            f"信号={c.get('prediction', {}).get('signal', 'N/A'):<8} "
            f"回撤={risk.get('max_drawdown_pct', 'N/A')}% "
            f"回撤事件={risk.get('drawdown_events', 'N/A')} "
            f"final_rank={score.get('final_rank', 'N/A')}"
        )

    late = result.get('late_session_plan', [])
    if late:
        lines.append('')
        lines.append('== 尾盘次日离场计划 ==')
        for plan in late:
            lines.append(
                f"  {plan['symbol']:<12} 入场 {plan['entry_price']:.2f} "
                f"→ 止盈 {plan['take_profit_price']:.2f}  兜底: {plan['fallback_exit']}"
            )
    return '\n'.join(lines)
