"""
data command: manage local stock data.
"""

from src.data.data_manager import (
    update_stock, load_stock, list_stock_files, verify_stock_data
)
from src.data.stock_registry import REGISTRY
from src.cli.colors import header, success, error, bold


def register(subparsers):
    p = subparsers.add_parser('data', help='data management')
    sub = p.add_subparsers(dest='data_action', required=True)

    sub.add_parser('list', help='list local stock data files').set_defaults(func=handle_list)

    p_update = sub.add_parser('update', help='update stock data')
    p_update.add_argument('symbol', nargs='?', help='stock symbol; empty updates all')
    p_update.set_defaults(func=handle_update)

    p_info = sub.add_parser('info', help='show stock data info')
    p_info.add_argument('symbol', nargs='?', help='stock symbol; empty lists registry')
    p_info.set_defaults(func=handle_info)

    p_verify = sub.add_parser('verify', help='verify recent local data against yfinance')
    p_verify.add_argument('symbol', help='stock symbol')
    p_verify.add_argument('--days', type=int, default=3, help='recent local rows to compare')
    p_verify.set_defaults(func=handle_verify)


def handle_list(args):
    files = list_stock_files()
    print(header('Local stock data files:'))
    for f in files:
        print(f'  {f}')


def handle_update(args):
    if args.symbol:
        res = update_stock(args.symbol)
        print(success(res['message']) if res.get('success') else error(res['message']))
        return

    for symbol in REGISTRY.list_symbols():
        res = update_stock(symbol)
        print(success(res['message']) if res.get('success') else error(res['message']))


def handle_info(args):
    if args.symbol:
        try:
            info = REGISTRY.get(args.symbol)
            df = load_stock(args.symbol)
            print(header(f'{info.symbol} {info.name}'))
            print(f'  Market: {info.market}')
            print(f'  Sector: {info.sector or "N/A"}')
            print(f'  Range: {df["date"].min()} ~ {df["date"].max()}')
            print(f'  Rows: {len(df)}')
            print(f'  Latest close: {df["close"].iloc[-1]:.2f}')
            if 'adj_close' in df.columns:
                print(f'  Latest adjusted close: {df["adj_close"].iloc[-1]:.2f}')
        except Exception as e:
            print(error(f'Load failed: {e}'))
        return

    print(header('Stock registry:'))
    for info in REGISTRY.list_all():
        print(f"  {bold(info.symbol)} {info.name} ({info.market}) [{info.sector or 'N/A'}]")


def handle_verify(args):
    result = verify_stock_data(args.symbol, days=args.days)
    printer = success if result.get('success') else error
    print(printer(result.get('message', 'verification failed')))
    print(f"  Symbol: {result.get('symbol')}")
    if 'rows_checked' in result:
        print(f"  Rows checked: {result['rows_checked']}")
        print(f"  Local latest: {result.get('latest_local_date')}")
        print(f"  Remote latest: {result.get('latest_remote_date')}")
    for mismatch in result.get('mismatches', []):
        print(
            f"  {mismatch['date']} {mismatch['column']}: "
            f"local={mismatch['local']} remote={mismatch['remote']}"
        )
