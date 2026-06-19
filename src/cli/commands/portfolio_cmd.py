"""
portfolio command: 组合账户状态、风险配置与组合级今日决策。

子命令：
  portfolio show
  portfolio set-cash 100000
  portfolio set-position 002156.SZ 800 --avg-cost 62.5 [--note manual]
  portfolio remove-position 002156.SZ
  portfolio risk-profile [set --max-total-position 0.40 ...]
  portfolio decide --mode close_after_market
  portfolio decide --mode open_realtime --open 002156.SZ=68.27
  portfolio decide --mode late_session --quote quotes.json
"""

import json

from src.portfolio.state import PortfolioStateManager
from src.portfolio.risk import RiskProfileManager
from src.portfolio.decision_engine import PortfolioDecisionEngine
from src.portfolio.schema import DecisionMode
from src.portfolio import reports
from src.data.data_manager import load_stock
from src.cli.colors import (
    header, subheader, success, warning, error, bold, dim, return_pct, drawdown_pct
)


def register(subparsers):
    p = subparsers.add_parser('portfolio', help='portfolio state, risk and decision')
    sub = p.add_subparsers(dest='portfolio_action', required=True)

    sub.add_parser('show', help='show cash, positions and exposure').set_defaults(func=handle_show)

    p_cash = sub.add_parser('set-cash', help='set available cash')
    p_cash.add_argument('amount', type=float)
    p_cash.set_defaults(func=handle_set_cash)

    p_pos = sub.add_parser('set-position', help='set a holding')
    p_pos.add_argument('symbol')
    p_pos.add_argument('shares', type=int)
    p_pos.add_argument('--avg-cost', type=float, help='average cost')
    p_pos.add_argument('--note', help='free-text note')
    p_pos.set_defaults(func=handle_set_position)

    p_rm = sub.add_parser('remove-position', help='remove a holding')
    p_rm.add_argument('symbol')
    p_rm.set_defaults(func=handle_remove_position)

    p_risk = sub.add_parser('risk-profile', help='show or set risk profile')
    risk_sub = p_risk.add_subparsers(dest='risk_action')
    p_risk.set_defaults(func=handle_risk_show)
    p_risk_set = risk_sub.add_parser('set', help='update risk parameters')
    for key, typ in _RISK_FIELDS:
        p_risk_set.add_argument(f'--{key.replace("_", "-")}', dest=key, type=typ)
    p_risk_set.set_defaults(func=handle_risk_set)

    p_bt = sub.add_parser('backtest', help='multi-stock joint portfolio backtest')
    p_bt.add_argument('--symbols', help='comma-separated subset; default = A-share universe')
    p_bt.add_argument('--start', help='start date YYYY-MM-DD')
    p_bt.add_argument('--end', help='end date YYYY-MM-DD')
    p_bt.add_argument('--capital', type=float, default=100000.0, help='total capital')
    p_bt.add_argument('--fee', type=float, default=5.0, help='fee per trade')
    p_bt.add_argument('--exec-price', dest='exec_price', choices=['close', 'open'],
                      default='close', help='execution price (default close, more realistic)')
    p_bt.add_argument('--walk-forward', dest='walk_forward', action='store_true',
                      help='select combos out-of-sample (no lookahead) instead of best_combos.json')
    p_bt.add_argument('--wf-train-days', dest='wf_train_days', type=int, default=180,
                      help='walk-forward training window in days')
    p_bt.add_argument('--wf-step-days', dest='wf_step_days', type=int, default=63,
                      help='walk-forward rebalance step in days')
    p_bt.add_argument('--trades', type=int, default=20, help='trades to print (0=all)')
    p_bt.set_defaults(func=handle_backtest)

    p_dec = sub.add_parser('decide', help='portfolio-level decision')
    p_dec.add_argument('--mode', choices=DecisionMode.ALL,
                       default=DecisionMode.CLOSE_AFTER_MARKET)
    p_dec.add_argument('--symbols', help='comma-separated subset of the universe')
    p_dec.add_argument('--open', action='append', default=[],
                       help='SYMBOL=open price (open_realtime mode), repeatable')
    p_dec.add_argument('--quote', help='path to a quotes JSON file (late_session mode)')
    p_dec.add_argument('--json', action='store_true', help='print raw JSON result')
    p_dec.set_defaults(func=handle_decide)


_RISK_FIELDS = [
    ('max_total_position', float),
    ('max_single_position', float),
    ('max_late_session_position', float),
    ('min_cash_ratio', float),
    ('drawdown_limit_pct', float),
    ('drawdown_event_threshold_pct', float),
    ('max_drawdown_events', int),
    ('rebalance_threshold', float),
    ('late_session_take_profit_pct', float),
    ('late_session_exit', str),
    ('risk_lookback_days', int),
    ('single_drawdown_limit_pct', float),
]


def _prices_for_state(state):
    prices = {}
    for symbol in state.positions:
        try:
            prices[symbol] = float(load_stock(symbol)['close'].iloc[-1])
        except Exception:
            pass
    return prices


def handle_show(args):
    mgr = PortfolioStateManager()
    state = mgr.load()
    prices = _prices_for_state(state)
    print(header('组合账户状态'))
    print(reports.format_state(state.to_dict(), prices))


def handle_set_cash(args):
    mgr = PortfolioStateManager()
    state = mgr.set_cash(args.amount)
    print(success(f'现金已设为 {state.cash:.2f}'))


def handle_set_position(args):
    mgr = PortfolioStateManager()
    try:
        state = mgr.set_position(args.symbol, args.shares,
                                 avg_cost=args.avg_cost, note=args.note)
    except ValueError as e:
        print(error(str(e)))
        return
    pos = state.positions[args.symbol]
    print(success(f'{args.symbol} 持仓已更新：{pos.shares} 股 @ 成本 {pos.avg_cost:.2f}'))


def handle_remove_position(args):
    mgr = PortfolioStateManager()
    mgr.remove_position(args.symbol)
    print(success(f'{args.symbol} 持仓已移除'))


def handle_risk_show(args):
    if getattr(args, 'risk_action', None) == 'set':
        return handle_risk_set(args)
    profile = RiskProfileManager().load()
    print(header('组合风险配置'))
    for key, _ in _RISK_FIELDS:
        print(f'  {key:<32} {getattr(profile, key)}')


def handle_risk_set(args):
    updates = {key: getattr(args, key, None) for key, _ in _RISK_FIELDS}
    updates = {k: v for k, v in updates.items() if v is not None}
    if not updates:
        print(warning('未提供任何风险参数'))
        return
    profile = RiskProfileManager().update(**updates)
    print(success('风险配置已更新：'))
    for key in updates:
        print(f'  {key} = {getattr(profile, key)}')


def _parse_open_prices(open_args):
    prices = {}
    for item in open_args or []:
        if '=' not in item:
            raise ValueError(f'--open 需要 SYMBOL=价格 格式，得到 {item}')
        symbol, value = item.split('=', 1)
        prices[symbol.strip()] = float(value)
    return prices


def _load_quotes(path):
    if not path:
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def handle_backtest(args):
    from src.portfolio.backtester import PortfolioBacktester
    from src.data.stock_registry import REGISTRY

    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',') if s.strip()]
    else:
        # 默认 A 股全集（排除美股，交易日历不同）
        symbols = [s for s in REGISTRY.list_symbols()
                   if REGISTRY.get(s).market != '美股']

    mode_label = 'walk-forward 样本外选组合' if args.walk_forward else 'best_combos.json 固定组合'
    print(header(f'组合联合回测（总本金 {args.capital:.0f}，{mode_label}）'))
    print(dim(f'一笔资金在多只股票间按组合风险约束联合分配，逐日滚动决策、{args.exec_price} 价成交。'))
    try:
        combo_plan = None
        if args.walk_forward:
            from src.portfolio.walkforward import WalkForwardSelector
            print(dim('正在构建 walk-forward 组合计划（仅用每个再平衡点之前的数据选组合）...'))
            selector = WalkForwardSelector(
                train_window_days=args.wf_train_days, step_days=args.wf_step_days,
                initial_capital=args.capital, fee_per_trade=args.fee)
            combo_plan = selector.build_plan(symbols, args.start, args.end)
        bt = PortfolioBacktester(symbols=symbols, initial_capital=args.capital,
                                 fee_per_trade=args.fee, execution_price=args.exec_price,
                                 combo_plan=combo_plan)
        res = bt.run(start_date=args.start, end_date=args.end)
    except Exception as e:
        print(error(f'回测失败: {e}'))
        return

    m = res['metrics']
    print()
    print(f"标的: {', '.join(m['symbols'])}")
    for sym, combo in m['combos'].items():
        print(dim(f'   {sym}: {combo}'))
    print(f"区间: {m['start_date']} ~ {m['end_date']}    交易日: {m['days']}")
    print(f"期末权益: {bold(format(m['final_value'], '.2f'))}")
    print(f"总收益率: {return_pct(m['total_return_pct'])}")
    print(f"最大回撤: {drawdown_pct(m['max_drawdown_pct'])}")
    print(f"回撤次数(>3%): {m['drawdown_events_3pct']}    回撤次数(>5%): {m['drawdown_events_5pct']}")
    print(f"平均股票敞口: {m['avg_exposure']*100:.1f}%    峰值敞口: {m['max_exposure']*100:.1f}%")
    print(f"日胜率: {m['win_rate']:.1f}%    夏普: {m['sharpe']:.2f}")
    print(f"交易笔数: {len(res['trades'])}")

    trades = res['trades']
    limit = len(trades) if args.trades == 0 else args.trades
    if trades:
        print()
        print(subheader(f'交易记录（前 {min(limit, len(trades))} / 共 {len(trades)} 笔）'))
        for t in trades[:limit]:
            action = success('买入') if t['action'] == 'buy' else warning('卖出')
            print(f"  {t['date']}  {action} {t['symbol']:<11} {t['shares']:>5}股 @ {t['price']:.2f}  {dim(t['reason'])}")


def handle_decide(args):
    symbols = None
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',') if s.strip()]

    try:
        open_prices = _parse_open_prices(args.open)
        quotes = _load_quotes(args.quote)
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(error(f'参数解析失败: {e}'))
        return

    engine = PortfolioDecisionEngine()
    try:
        result = engine.decide(args.mode, symbols=symbols,
                               quotes=quotes, open_prices=open_prices)
    except Exception as e:
        print(error(f'决策失败: {e}'))
        return

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(header(f'组合决策（{args.mode}）'))
    print(dim('提示：以下为决策建议，非真实下单。'))
    print()
    print(reports.format_decision(result))
