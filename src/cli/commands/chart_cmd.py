"""
chart 命令：在终端绘制 ASCII K 线图

用法：
    strategy chart SYMBOL [--start DATE] [--end DATE]
"""

import math
from datetime import datetime

import pandas as pd

from src.data.data_manager import load_stock
from src.cli.colors import header, success, error, bold, return_pct
from src.cli.completer import resolve_symbols


def register(subparsers):
    p = subparsers.add_parser('chart', help='在终端绘制 K 线图（ASCII）')
    p.add_argument('symbol', nargs='?', help='股票代码；省略进入交互选择')
    p.add_argument('--start', help='开始日期 (YYYY-MM-DD)，默认最近 60 个交易日')
    p.add_argument('--end', help='结束日期 (YYYY-MM-DD)，默认今天')
    p.add_argument('--width', '-w', type=int, default=80, help='图表宽度（字符）')
    p.add_argument('--height', '-H', type=int, default=20, help='K线区域高度（字符）')
    p.add_argument('--bars', '-b', type=int, default=60, help='显示 K 线数量')
    p.add_argument('--ma', help='逗号分隔的均线周期，如 5,20,60')
    p.add_argument('--no-volume', action='store_true', help='不显示成交量')
    p.add_argument('--us-style', action='store_true', help='美股颜色：绿涨红跌')
    p.set_defaults(func=handle)


def _color_for_candle(open_price, close_price, us_style=False):
    if close_price >= open_price:
        return ('green', '▲' if not us_style else '▼')
    return ('red', '▼' if not us_style else '▲')


def _format_date(d):
    if isinstance(d, str):
        return d[:10]
    return str(d)[:10]


def _compute_ma(series, window):
    if len(series) < window:
        return [None] * len(series)
    return series.rolling(window=window).mean().tolist()


def _render_candle(open_price, high, low, close_price, min_price, price_range, height):
    def price_to_row(p):
        if price_range <= 0:
            return 0
        ratio = (p - min_price) / price_range
        row = int(round(ratio * (height - 1)))
        return max(0, min(height - 1, row))

    top = price_to_row(max(open_price, close_price))
    bottom = price_to_row(min(open_price, close_price))
    wick_top = price_to_row(high)
    wick_bottom = price_to_row(low)

    return {
        'wick_top': wick_top,
        'top': top,
        'bottom': bottom,
        'wick_bottom': wick_bottom,
        'is_up': close_price >= open_price
    }


def handle(args):
    symbols = resolve_symbols([args.symbol] if args.symbol else [], allow_multiple=False)
    if not symbols:
        return
    symbol = symbols[0]

    try:
        df = load_stock(symbol)
    except Exception as e:
        print(error(f'加载股票数据失败：{e}'))
        return

    df = df.sort_values('date').reset_index(drop=True)

    if args.end:
        end_date = pd.to_datetime(args.end).date()
        df = df[df['date'] <= end_date]
    if args.start:
        start_date = pd.to_datetime(args.start).date()
        df = df[df['date'] >= start_date]
    else:
        df = df.tail(args.bars)

    if len(df) == 0:
        print(error('筛选后无数据'))
        return

    if len(df) > args.bars:
        df = df.tail(args.bars)

    df = df.reset_index(drop=True)
    n = len(df)
    ohlc = df[['date', 'open', 'high', 'low', 'close', 'volume']].to_dict('records')

    ma_periods = []
    if args.ma:
        ma_periods = [int(x.strip()) for x in args.ma.split(',') if x.strip().isdigit()]

    ma_values = {}
    for period in ma_periods:
        ma_values[period] = _compute_ma(df['close'], period)

    min_price = min(r['low'] for r in ohlc)
    max_price = max(r['high'] for r in ohlc)
    price_range = max_price - min_price
    if price_range <= 0:
        price_range = 1e-6

    max_volume = max(r['volume'] for r in ohlc) if not args.no_volume else 1

    height = args.height
    width = args.width

    print(header(f'\n【{symbol} ASCII K 线图】'))
    print(f'区间：{_format_date(ohlc[0]["date"])} ~ {_format_date(ohlc[-1]["date"])}  共 {n} 根K线')
    print(f'价格范围：{min_price:.2f} ~ {max_price:.2f}')
    print()

    candles = []
    for idx, row in enumerate(ohlc):
        c = _render_candle(row['open'], row['high'], row['low'], row['close'],
                           min_price, price_range, height)
        c['date'] = _format_date(row['date'])
        c['open'] = row['open']
        c['close'] = row['close']
        c['high'] = row['high']
        c['low'] = row['low']
        c['volume'] = row['volume']
        c['color'], c['direction'] = _color_for_candle(row['open'], row['close'], args.us_style)
        for period, ma_series in ma_values.items():
            c[f'ma{period}'] = ma_series[df.index[idx]]
        candles.append(c)

    GREEN = '\033[32m'
    RED = '\033[31m'
    BLUE = '\033[34m'
    YELLOW = '\033[33m'
    CYAN = '\033[36m'
    RESET = '\033[0m'

    for row in range(height - 1, -1, -1):
        price_level = min_price + (row / (height - 1)) * price_range if height > 1 else min_price
        line = f'{price_level:>8.2f} │'

        for c in candles:
            char = ' '
            color = ''
            wick_top, top, bottom, wick_bottom = c['wick_top'], c['top'], c['bottom'], c['wick_bottom']

            if wick_top >= row >= wick_bottom:
                if top >= row >= bottom:
                    char = '█'
                else:
                    char = '│'
                color = GREEN if c['is_up'] else RED

            for period in ma_periods:
                ma_val = c.get(f'ma{period}')
                if ma_val is not None and not math.isnan(ma_val):
                    ma_row = int(round((ma_val - min_price) / price_range * (height - 1)))
                    ma_row = max(0, min(height - 1, ma_row))
                    if ma_row == row and not (wick_top >= row >= wick_bottom):
                        char = '·'
                        if period == 5:
                            color = YELLOW
                        elif period == 20:
                            color = CYAN
                        else:
                            color = BLUE

            line += color + char + RESET

        print(line)

    date_line = '         └'
    step = max(1, n // 6)
    for i in range(n):
        if i % step == 0 or i == n - 1:
            date_line += candles[i]['date'][5:7] + candles[i]['date'][8:10]
        else:
            date_line += '  '
    print(date_line[:width + 12])

    if not args.no_volume:
        print()
        print(header('成交量'))
        vol_height = 5
        for row in range(vol_height - 1, -1, -1):
            vol_line = '         │'
            for c in candles:
                vol_ratio = c['volume'] / max_volume if max_volume > 0 else 0
                vol_row = int(round(vol_ratio * (vol_height - 1)))
                if vol_row >= row:
                    color = GREEN if c['is_up'] else RED
                    vol_line += color + '▌' + RESET
                else:
                    vol_line += ' '
            print(vol_line)

    print()
    legend = '图例：' + GREEN + '█ 涨' + RESET + '  ' + RED + '█ 跌' + RESET
    for period in ma_periods:
        if period == 5:
            legend += '  ' + YELLOW + f'· MA{period}' + RESET
        elif period == 20:
            legend += '  ' + CYAN + f'· MA{period}' + RESET
        else:
            legend += '  ' + BLUE + f'· MA{period}' + RESET
    print(legend)

    last = candles[-1]
    change_pct = (last['close'] - last['open']) / last['open'] * 100 if last['open'] != 0 else 0
    print(f'\n最新：{_format_date(last["date"])}  开:{last["open"]:.2f} 高:{last["high"]:.2f} '
          f'低:{last["low"]:.2f} 收:{last["close"]:.2f} 涨跌:{return_pct(change_pct)}')
