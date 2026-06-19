"""
scan command: scan pipeline/strategy combinations over a date range.
"""

from datetime import datetime

from src.data.stock_registry import REGISTRY
from src.backtest.combo_scanner import scan_best_combo
from src.analysis.best_combo_registry import BestComboRegistry
from src.cli.colors import (
    header, subheader, success, warning, error,
    return_pct, drawdown_pct, bold, dim
)
from src.cli.completer import resolve_symbols


def register(subparsers):
    p = subparsers.add_parser('scan', help='scan best combo')
    p.add_argument('symbols', nargs='*', help='stock symbols; empty scans all selected symbols')
    p.add_argument('--start', default='2024-06-01', help='start date')
    p.add_argument('--end', help='end date; default today')
    p.add_argument('--max-drawdown', '-md', type=float, default=5.0,
                   help='maximum drawdown constraint percent, default 5')
    p.add_argument('--stop-loss', '-sl', type=float, default=None,
                   help='portfolio drawdown stop loss percent, e.g. 5')
    p.add_argument('--save', action='store_true', default=True,
                   help='save best combo to registry')
    p.add_argument('--no-save', dest='save', action='store_false',
                   help='do not save best combo')
    p.add_argument('--pipelines', help='comma-separated pipeline names')
    p.add_argument('--strategies', help='comma-separated strategy names')
    p.set_defaults(func=handle)


def _parse_list(value):
    return [x.strip() for x in value.split(',') if x.strip()] if value else None


def handle(args):
    symbols = resolve_symbols(args.symbols, allow_multiple=True)
    if not symbols:
        return

    pipelines = _parse_list(args.pipelines)
    strategies = _parse_list(args.strategies)
    end = args.end or datetime.now().date().isoformat()
    stop_loss = args.stop_loss / 100.0 if args.stop_loss else None
    registry = BestComboRegistry() if args.save else None

    print(header(f'\nCombo scan ({args.start} ~ {end})'))
    print(dim(f'Symbols: {" ".join(symbols) or "all"}'))
    print()

    rows = []
    for symbol in symbols:
        info = REGISTRY.get(symbol)
        print(subheader(f'[{symbol}] {info.name}'))
        try:
            result = scan_best_combo(
                symbol, start_date=args.start, end_date=end,
                max_drawdown_pct=args.max_drawdown,
                stop_loss_pct=stop_loss,
                pipelines=pipelines, strategies=strategies
            )
            best = result['best']
            relaxed = result['constraint_relaxed']
            rankings = [
                r for r in result['all_rankings']
                if r.get('total_return_pct', -999) > -900
            ]
            if best and best.get('total_return_pct', -999) > -900:
                if relaxed:
                    print(warning('  No combo satisfied drawdown constraint; selected lowest drawdown.'))
                print(f"  Best: {bold(best['pipeline'])} + {bold(best['strategy'])}")
                print(f"  Return: {return_pct(best['total_return_pct'])}")
                print(f"  Max drawdown: {drawdown_pct(best['max_drawdown_pct'], args.max_drawdown)}")
                print(f"  Buy & hold: {return_pct(best.get('buy_hold_return_pct', 0.0))}")
                print(f"  Excess: {return_pct(best.get('excess_return_pct', 0.0))}")
                print(f"  Sharpe: {best['sharpe']:.3f}")
                print(f"  Trades: {best['trade_count']}")

                if registry:
                    registry.update_from_scan(
                        symbol=symbol,
                        pipeline_name=best['pipeline'],
                        strategy_id=best['strategy'],
                        metrics={
                            'total_return_pct': best['total_return_pct'],
                            'max_drawdown_pct': best['max_drawdown_pct'],
                            'buy_hold_return_pct': best.get('buy_hold_return_pct'),
                            'excess_return_pct': best.get('excess_return_pct'),
                            'trade_count': best['trade_count'],
                            'sharpe': best['sharpe']
                        },
                        time_range={'start': args.start, 'end': end}
                    )
                    print(success('  Saved best combo.'))

                print(dim('  Valid ranking:'))
                rank_rows = []
                for rank, item in enumerate(rankings[:10], start=1):
                    rank_rows.append([
                        rank,
                        f"{item['pipeline']}+{item['strategy']}",
                        f"{item['total_return_pct']:.2f}%",
                        f"{item['max_drawdown_pct']:.2f}%",
                        f"{item.get('excess_return_pct', 0.0):.2f}%",
                        'Y' if item.get('beats_buy_hold') else 'N',
                    ])
                _print_table(rank_rows, ['#', 'combo', 'return', 'drawdown', 'excess', 'beats B&H'])

                rows.append([
                    symbol,
                    f"{best['pipeline']}+{best['strategy']}",
                    f"{best['total_return_pct']:.2f}%",
                    f"{best['max_drawdown_pct']:.2f}%",
                    f"{best.get('excess_return_pct', 0.0):.2f}%",
                    f"{best['sharpe']:.3f}",
                    str(best['trade_count']),
                    warning('yes') if relaxed else success('no')
                ])
            else:
                print(error('  No valid combo.'))
        except Exception as e:
            print(error(f'  Scan failed: {e}'))
        print()

    if rows:
        print(header('Summary'))
        _print_table(rows, [
            'symbol', 'best combo', 'return', 'drawdown',
            'excess', 'sharpe', 'trades', 'relaxed'
        ])


def _print_table(rows, headers):
    if not rows:
        return
    col_widths = [max(len(str(row[i])) for row in [headers] + rows)
                  for i in range(len(headers))]
    sep = ' | '

    def fmt(row):
        return sep.join(str(row[i]).ljust(col_widths[i]) for i in range(len(row)))

    print(dim('-' * (sum(col_widths) + len(sep) * (len(headers) - 1))))
    print(bold(fmt(headers)))
    print(dim('-' * (sum(col_widths) + len(sep) * (len(headers) - 1))))
    for row in rows:
        print(fmt(row))
    print(dim('-' * (sum(col_widths) + len(sep) * (len(headers) - 1))))
