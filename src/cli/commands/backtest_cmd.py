"""
backtest command: run one pipeline + strategy combination.
"""

from src.backtest.combo_backtester import ComboBacktester
from src.cli.colors import (
    header, return_pct, drawdown_pct, bold, error
)
from src.cli.completer import resolve_backtest_args


def register(subparsers):
    p = subparsers.add_parser('backtest', help='run a single combo backtest')
    p.add_argument('symbol', nargs='?', help='stock symbol')
    p.add_argument('pipeline', nargs='?', help='pipeline name')
    p.add_argument('strategy', nargs='?', help='strategy name')
    p.add_argument('--start', help='start date (YYYY-MM-DD)')
    p.add_argument('--end', help='end date (YYYY-MM-DD)')
    p.add_argument('--capital', type=float, default=100000, help='initial capital')
    p.add_argument('--fee', type=float, default=5, help='fee per trade')
    p.add_argument('--lot', type=int, default=100, help='lot size')
    p.add_argument('--stop-loss', type=float, default=None,
                   help='portfolio drawdown stop loss percent, e.g. 5')
    p.set_defaults(func=handle)


def handle(args):
    resolved = resolve_backtest_args(args)
    if not resolved:
        return
    symbol, pipeline, strategy = resolved

    stop_loss = args.stop_loss / 100.0 if args.stop_loss else None
    try:
        bt = ComboBacktester(
            symbol, pipeline, strategy,
            initial_capital=args.capital,
            fee_per_trade=args.fee,
            lot_size=args.lot,
            stop_loss_pct=stop_loss
        )
        result = bt.run(start_date=args.start, end_date=args.end)
    except Exception as e:
        print(error(f'Backtest failed: {e}'))
        return

    m = result['metrics']
    print(header(f"Backtest: {m['symbol']} | {bold(m['pipeline'])} | {bold(m['strategy'])}"))
    print(f"  Range: {m['start_date']} ~ {m['end_date']}")
    print(f"  Return: {return_pct(m['total_return_pct'])}")
    print(f"  Max drawdown: {drawdown_pct(m['max_drawdown_pct'])}")
    print(f"  Buy & hold: {return_pct(m.get('buy_hold_return_pct', 0.0))}")
    print(f"  Buy & hold drawdown: {drawdown_pct(m.get('buy_hold_max_drawdown_pct', 0.0))}")
    print(f"  Excess return: {return_pct(m.get('excess_return_pct', 0.0))}")
    if m.get('benchmark_available'):
        print(f"  Benchmark {m.get('benchmark')}: {return_pct(m.get('benchmark_return_pct', 0.0))}")
    print(f"  Trades: {m['trade_count']}")
    print(f"  Win rate: {m['win_rate']:.2f}%")
    print(f"  Sharpe: {m['sharpe']:.3f}")
    print(f"  Final value: {m['final_value']:,.2f}")
    print(f"  Total fees: {m['total_fees']:,.2f}")
