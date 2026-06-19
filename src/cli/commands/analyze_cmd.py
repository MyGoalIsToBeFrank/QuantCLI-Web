"""
analyze 命令：季度策略分析

用法：
    strategy analyze [SYMBOL ...] [--start DATE] [--end DATE] [--save]
    省略 SYMBOL 时分析所有注册股票。
"""

from datetime import datetime

from src.data.stock_registry import REGISTRY
from src.analysis.quarterly_analyzer import QuarterlyAnalyzer
from src.analysis.best_combo_registry import BestComboRegistry
from src.cli.colors import (
    header, subheader, success, warning, error,
    return_pct, drawdown_pct, bold, dim
)
from src.cli.completer import resolve_symbols


def register(subparsers):
    p = subparsers.add_parser('analyze', help='季度策略分析')
    p.add_argument('symbols', nargs='*', help='股票代码；省略则分析全部')
    p.add_argument('--start', default='2024-06-01', help='开始日期')
    p.add_argument('--end', help='结束日期，默认今天')
    p.add_argument('--pipelines', help='逗号分隔的 Pipeline 列表，默认全部')
    p.add_argument('--strategies', help='逗号分隔的 Strategy 列表，默认全部')
    p.add_argument('--max-drawdown', '-md', type=float, default=None,
                   help='最大回撤约束（%%），如 5 表示回撤不得超过 5%%')
    p.add_argument('--save', action='store_true', default=True, help='保存最佳组合到注册表（默认开启）')
    p.add_argument('--no-save', dest='save', action='store_false', help='不保存最佳组合到注册表')
    p.set_defaults(func=handle)


def _parse_list(s):
    return [x.strip() for x in s.split(',') if x.strip()] if s else None


def handle(args):
    symbols = resolve_symbols(args.symbols, allow_multiple=True)
    if not symbols:
        return
    pipelines = _parse_list(args.pipelines)
    strategies = _parse_list(args.strategies)
    end = args.end or datetime.now().date().isoformat()

    analyzer = QuarterlyAnalyzer()
    registry = BestComboRegistry() if args.save else None

    print(header(f'\n季度策略分析（{args.start} ~ {end}）'))
    print(dim(f'股票：{" ".join(symbols) or "全部"}'))
    print()

    for symbol in symbols:
        info = REGISTRY.get(symbol)
        print(subheader(f'[{symbol}] {info.name}'))
        try:
            result = analyzer.analyze_symbol(
                symbol, args.start, end,
                pipelines=pipelines, strategies=strategies,
                max_drawdown_pct=args.max_drawdown
            )
            q = result['quarters'][-1]
            best = q['best']
            relaxed = q.get('constraint_relaxed', False)
            if best and best.get('total_return_pct', -999) > -900:
                if relaxed:
                    print(warning('  未找到满足回撤约束的组合，已放宽至回撤最小者'))
                print(f"  最佳组合：{bold(best['pipeline'])} + {bold(best['strategy'])}")
                print(f"  收益率：{return_pct(best['total_return_pct'])}")
                print(f"  最大回撤：{drawdown_pct(best['max_drawdown_pct'], args.max_drawdown or 5.0)}")
                print(f"  夏普：{best['sharpe']:.3f}")
                print(f"  交易次数：{best['trade_count']}")
            else:
                print(error('  无有效组合'))

            if args.save and registry:
                registry.update_from_analysis(
                    result,
                    time_range={'start': args.start, 'end': end}
                )
                print(success('  已保存最佳组合'))
        except Exception as e:
            print(error(f'  分析失败：{e}'))
        print()

    if args.save:
        print(success('最佳组合已保存到 data/best_combos.json'))
