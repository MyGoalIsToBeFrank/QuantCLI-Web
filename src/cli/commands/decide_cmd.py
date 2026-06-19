"""
decide command: produce today's decision for one or more symbols.
"""

from datetime import datetime

from src.data.data_manager import load_stock
from src.pipeline_registry import PIPELINE_REGISTRY
from src.strategy_registry import STRATEGY_REGISTRY
from src.analysis.best_combo_registry import BestComboRegistry
from src.strategy import calculate_trade_shares
from src.backtest.combo_backtester import build_latest_open_decision_frame
from src.cli.colors import (
    header, success, warning, error, return_pct, bold
)
from src.cli.completer import resolve_symbols


def register(subparsers):
    p = subparsers.add_parser('decide', help='today decision')
    p.add_argument('symbols', nargs='*', help='stock symbols; empty uses saved best combos')
    p.add_argument('--pipeline', '-p', help='pipeline name')
    p.add_argument('--strategy', '-st', help='strategy name')
    p.add_argument('--open', '-o', type=float, help='known decision-day open price')
    p.add_argument('--decision-mode', choices=['auto', 'open', 'close'], default='auto',
                   help='auto uses open when explicitly available; close uses completed bars only')
    p.add_argument('--capital', type=float, default=100000, help='capital')
    p.add_argument('--fee', type=float, default=5, help='fee per trade')
    p.add_argument('--lot', type=int, default=100, help='lot size')
    p.set_defaults(func=handle)


def _resolve_combo(args, symbol):
    if args.pipeline and args.strategy:
        return args.pipeline, args.strategy, None

    combo = BestComboRegistry().get(symbol)
    if not combo:
        raise ValueError(f'{symbol} has no saved best combo; run scan/analyze first')

    pipeline_name = combo.get('pipeline_name') or combo.get('pipeline')
    strategy_name = combo.get('strategy_id') or combo.get('strategy')
    return pipeline_name, strategy_name, combo


def _should_use_open(args, last_date, today):
    if args.decision_mode == 'open':
        return True
    if args.decision_mode == 'close':
        return False
    return args.open is not None or str(last_date) == str(today)


def handle(args):
    if args.symbols:
        symbols = list(args.symbols)
    else:
        symbols = BestComboRegistry().list_symbols()
        if not symbols:
            symbols = resolve_symbols([], allow_multiple=True)

    today = datetime.now().date()
    if not symbols:
        print(warning('No symbols to decide.'))
        return

    print(header(f'\nToday decision ({today})'))
    print()

    for symbol in symbols:
        try:
            pipeline_name, strategy_name, combo = _resolve_combo(args, symbol)
            raw_df = load_stock(symbol)
            last_date = raw_df['date'].iloc[-1]

            t_open = args.open
            if t_open is None:
                if str(last_date) == str(today):
                    t_open = float(raw_df['open'].iloc[-1])
                else:
                    t_open = float(raw_df['close'].iloc[-1])
            t_open = float(t_open)

            use_open = _should_use_open(args, last_date, today)
            if use_open:
                fit_df = build_latest_open_decision_frame(raw_df, t_open, today)
            else:
                fit_df = raw_df

            pipeline = PIPELINE_REGISTRY.create(pipeline_name)
            strategy = STRATEGY_REGISTRY.create(strategy_name)
            pipeline.fit(fit_df)
            pred = pipeline.predict()

            t_minus_1_close = float(raw_df['close'].iloc[-1]) if use_open else (
                float(raw_df['close'].iloc[-2]) if len(raw_df) > 1 else t_open
            )
            gap_pct = (t_open / t_minus_1_close - 1) * 100 if t_minus_1_close else 0.0

            context = {
                'current_position': 0.0,
                'cash': args.capital,
                'shares': 0,
                'open_price': t_open,
                'close_price': float(raw_df['close'].iloc[-1]),
                'prev_close': t_minus_1_close,
                'fee_per_trade': args.fee,
                'lot_size': args.lot,
                'signal_threshold': 0.10
            }
            decision = strategy.decide(pred, context)
            target_position = decision['target_position']
            trade_shares = calculate_trade_shares(
                args.capital, 0, t_open, target_position, args.fee, args.lot
            )

            print(header('=' * 60))
            print(header(f'[{symbol}] decision'))
            if combo:
                time_range = combo.get('time_range', {})
                print(f'Combo: {bold(pipeline_name)} + {bold(strategy_name)} '
                      f'({time_range.get("start", "N/A")} ~ {time_range.get("end", "N/A")})')
            else:
                print(f'Combo: {bold(pipeline_name)} + {bold(strategy_name)} (manual)')
            print(f'Data latest: {last_date}')
            print(f'Decision mode: {"open" if use_open else "close"}')
            print(f'Reference price: {t_open:.2f}')
            print(f'Gap: {return_pct(gap_pct)}')
            print(f'Prediction: {pred}')
            print(f'Decision: {decision["note"]}')
            print(f'Target position: {target_position * 100:.1f}%')
            if trade_shares > 0:
                print(success(f'Action: buy {trade_shares} shares'))
            elif trade_shares < 0:
                print(warning(f'Action: sell {abs(trade_shares)} shares'))
            else:
                print('Action: hold')
        except Exception as e:
            print(error(f'[{symbol}] decision failed: {e}'))
